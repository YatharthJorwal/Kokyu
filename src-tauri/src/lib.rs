// The Kōkyū shell: one window, the tray, the API key store, and the kernel as a
// hidden child process. Everything else lives in the kernel (KASANE/).

mod credentials;

use std::io::Write;
use std::net::{SocketAddr, TcpStream};
use std::os::windows::process::CommandExt;
use std::path::PathBuf;
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use tauri::{
    image::Image,
    menu::{Menu, MenuItem},
    tray::{TrayIcon, TrayIconBuilder},
    Manager, WindowEvent,
};

/// The kernel's address (D-027). It binds loopback only.
const KERNEL_ADDR: &str = "127.0.0.1:8780";
const KERNEL_PORT: u16 = 8780;

/// Win32 CREATE_NO_WINDOW: a child process gets no console window.
const CREATE_NO_WINDOW: u32 = 0x08000000;

/// True while `spawn_kernel`'s thread runs, so Reconnect never starts a second kernel.
static SPAWNING: AtomicBool = AtomicBool::new(false);

/// Shown on the tray while a camera stream is open (K2-07, FR-C-4): the camera is
/// never used without a visible sign.
const CAMERA_ACTIVE_TRAY_ICON: &[u8] = include_bytes!("../icons/tray-camera-active.png");

struct TrayIconHandle(TrayIcon);

/// The kernel process, so tray Quit can shut it down.
struct KernelChild(Arc<Mutex<Option<Child>>>);

/// The write end of the kernel's stdin (D-059): a key saved or removed in the app
/// reaches the running kernel as one JSON line, so no restart. Nothing else uses
/// this pipe, and no key ever crosses the websocket.
#[derive(Clone, Default)]
struct KernelPipe(Arc<Mutex<Option<ChildStdin>>>);

impl KernelPipe {
    /// Whether the running kernel got the change now (false: it uses it from the next start).
    fn send(&self, provider: &str, key: Option<&str>) -> bool {
        let Ok(mut guard) = self.0.lock() else { return false };
        let Some(stdin) = guard.as_mut() else { return false };
        let line = serde_json::json!({ "provider": provider, "key": key }).to_string();
        if writeln!(stdin, "{line}").and_then(|_| stdin.flush()).is_ok() {
            return true;
        }
        *guard = None; // the kernel is gone; the key is saved for the next start
        false
    }
}

/// Only the main window may change a key: the pet and other windows never show
/// the key dialog.
fn require_main(window: &tauri::WebviewWindow) -> Result<(), String> {
    if window.label() == "main" {
        Ok(())
    } else {
        Err("API keys can only be changed from the main window".into())
    }
}

/// Saves the API key for `provider` in the Windows Credential Manager and hands it
/// to the running kernel (FR-R-6, D-059). One key at a time: any other provider's
/// saved key is removed. Returns whether the kernel got it now. Never returns the
/// key, or any part of it.
#[tauri::command]
async fn set_api_key(
    window: tauri::WebviewWindow,
    pipe: tauri::State<'_, KernelPipe>,
    provider: String,
    key: String,
) -> Result<bool, String> {
    require_main(&window)?;
    let pipe = pipe.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        let key = credentials::clean_key(&key)?;
        // The new key is written first: a failure here must not lose the old one.
        credentials::set(&provider, &key)?;
        let mut leftover = Ok(());
        for other in credentials::list()? {
            if other != provider {
                if let Err(err) = credentials::delete(&other) {
                    leftover = Err(format!("saved, but the old {other} key could not be removed ({err})"));
                }
            }
        }
        let live = pipe.send(&provider, Some(&key));
        leftover.map(|()| live)
    })
    .await
    .map_err(|_| "saving the key was interrupted".to_string())?
}

/// Removes the saved API key for `provider`, here and in the running kernel.
/// Removing a key that is not there is fine.
#[tauri::command]
async fn delete_api_key(
    window: tauri::WebviewWindow,
    pipe: tauri::State<'_, KernelPipe>,
    provider: String,
) -> Result<bool, String> {
    require_main(&window)?;
    let pipe = pipe.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        credentials::delete(&provider)?;
        Ok(pipe.send(&provider, None))
    })
    .await
    .map_err(|_| "removing the key was interrupted".to_string())?
}

/// The tray shows the camera icon while a camera stream is open.
/// The disconnect banner's Reconnect (D-082): starts the kernel again when it has
/// exited or never started. One still running is left alone; the window's socket
/// keeps retrying it. Returns whether a start was begun.
#[tauri::command]
fn restart_kernel(kernel: tauri::State<'_, KernelChild>, pipe: tauri::State<'_, KernelPipe>) -> bool {
    if SPAWNING.load(Ordering::SeqCst) {
        return false;
    }
    let exited = match kernel.0.lock() {
        Ok(mut slot) => slot.as_mut().map_or(true, |child| matches!(child.try_wait(), Ok(Some(_)))),
        Err(_) => false,
    };
    if exited {
        spawn_kernel(kernel.0.clone(), pipe.inner().clone());
    }
    exited
}

#[tauri::command]
fn set_camera_indicator(
    app: tauri::AppHandle,
    tray: tauri::State<TrayIconHandle>,
    active: bool,
) -> Result<(), String> {
    let icon = if active {
        Image::from_bytes(CAMERA_ACTIVE_TRAY_ICON).map_err(|e| e.to_string())?
    } else {
        app.default_window_icon()
            .cloned()
            .ok_or_else(|| "no default window icon configured".to_string())?
    };
    tray.0.set_icon(Some(icon)).map_err(|e| e.to_string())
}

/// Puts this process, and so every child it spawns, into a Job Object that
/// Windows closes when this process dies for any reason (tray Quit, End Task,
/// Ctrl+C, a crash): the kernel, llama-server and GPT-SoVITS never outlive the
/// app. The handle is leaked on purpose: closing it would end the children.
#[cfg(windows)]
fn install_kill_on_close_job() {
    let result = (|| -> Result<win32job::Job, Box<dyn std::error::Error>> {
        let job = win32job::Job::create()?;
        let mut info = job.query_extended_limit_info()?;
        info.limit_kill_on_job_close();
        job.set_extended_limit_info(&mut info)?;
        job.assign_current_process()?;
        Ok(job)
    })();
    match result {
        Ok(job) => std::mem::forget(job),
        Err(e) => eprintln!(
            "[kokyu] could not set up the kill-on-close job ({e}); child processes may outlive \
             the app if it is ended from Task Manager"
        ),
    }
}

pub fn run() {
    // Before any child starts: children join the job only from a parent already in it.
    #[cfg(windows)]
    install_kill_on_close_job();

    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![set_camera_indicator, set_api_key, delete_api_key, restart_kernel])
        .setup(|app| {
            let window = app
                .get_webview_window("main")
                .expect("main window must exist -- check the label in tauri.conf.json");
            let _ = window.center();
            build_tray(app)?;

            let kernel = Arc::new(Mutex::new(None));
            let pipe = KernelPipe::default();
            spawn_kernel(kernel.clone(), pipe.clone());
            app.manage(KernelChild(kernel));
            app.manage(pipe);
            Ok(())
        })
        .on_window_event(|window, event| {
            // Closing the window hides it; the tray's Quit ends the app.
            if let WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let _ = window.hide();
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running Kōkyū");
}

/// Starts the kernel as a hidden child, logging to logs/kasane.log (D-060, D-089). On its
/// own thread, so the window never waits for the stale-port sweep or the spawn.
/// The kernel starts everything else itself, when it is needed.
///
/// Paths are relative to src-tauri/ (this binary's working directory under
/// `tauri dev`). Not verified for a packaged build (K1b).
fn spawn_kernel(kernel: Arc<Mutex<Option<Child>>>, pipe: KernelPipe) {
    SPAWNING.store(true, Ordering::SeqCst);
    std::thread::spawn(move || {
        spawn_kernel_now(&kernel, &pipe);
        SPAWNING.store(false, Ordering::SeqCst);
    });
}

fn spawn_kernel_now(kernel: &Arc<Mutex<Option<Child>>>, pipe: &KernelPipe) {
    {
        let logs_dir = PathBuf::from("../logs");
        let _ = std::fs::create_dir_all(&logs_dir);
        kill_stale_kernel();

        // The virtualenv lives at the repo root (.venv): one environment for the repo.
        let python = PathBuf::from("../.venv/Scripts/python.exe");
        if !python.exists() {
            eprintln!(
                "[kokyu] {} not found -- the Python venv is not set up yet. Run \
                 `python -m venv .venv` and `.venv\\Scripts\\python.exe -m pip install -r \
                 KASANE/requirements-dev.txt` from the repo root first (see README).",
                python.display()
            );
            return;
        }

        let mut cmd = Command::new(&python);
        cmd.arg("app.py")
            .current_dir("../KASANE")
            // Without this, Python buffers its log lines once stdout is a file.
            .env("PYTHONUNBUFFERED", "1");
        // FR-R-6, D-059: the saved API key goes to the kernel at spawn, in the
        // environment (the kernel removes it at import, before it starts any child),
        // never on the command line. Later changes go down the stdin pipe.
        match credentials::all() {
            Ok(keys) if !keys.is_empty() => {
                let map: serde_json::Map<String, serde_json::Value> =
                    keys.into_iter().map(|(provider, key)| (provider, serde_json::Value::String(key))).collect();
                cmd.env("KOKYU_API_KEYS", serde_json::Value::Object(map).to_string());
            }
            Ok(_) => {}
            Err(err) => eprintln!("[kokyu] keys: could not read the saved API key ({err})"),
        }
        cmd.env("KOKYU_KEY_PIPE", "1").stdin(Stdio::piped());

        let log = match std::fs::File::create(logs_dir.join("kasane.log")) {
            Ok(file) => file,
            Err(e) => {
                eprintln!("[kokyu] could not open logs/kasane.log: {e}");
                return;
            }
        };
        let Ok(log_err) = log.try_clone() else {
            eprintln!("[kokyu] could not duplicate the kernel log handle");
            return;
        };
        match cmd
            .creation_flags(CREATE_NO_WINDOW)
            .stdout(Stdio::from(log))
            .stderr(Stdio::from(log_err))
            .spawn()
        {
            Ok(mut child) => {
                if let Ok(mut stdin) = pipe.0.lock() {
                    *stdin = child.stdin.take();
                }
                if let Ok(mut slot) = kernel.lock() {
                    *slot = Some(child);
                }
            }
            Err(e) => eprintln!("[kokyu] failed to start the kernel: {e}"),
        }
    }
}

/// A kernel left running by an earlier run (a crash before the Job Object existed,
/// a manual `python app.py`) still holds the port; the new one could not bind.
/// Only a Python process is ever ended: anything else on the port is reported.
fn kill_stale_kernel() {
    let output = match Command::new("netstat").args(["-ano", "-p", "TCP"]).creation_flags(CREATE_NO_WINDOW).output() {
        Ok(o) => o,
        Err(e) => {
            eprintln!("[kokyu] startup sweep: could not run netstat ({e})");
            return;
        }
    };
    let suffix = format!(":{KERNEL_PORT}");
    let mut pids: Vec<u32> = Vec::new();
    for line in String::from_utf8_lossy(&output.stdout).lines() {
        // Proto  Local Address  Foreign Address  State  PID
        let cols: Vec<&str> = line.split_whitespace().collect();
        if cols.len() >= 5 && cols[0] == "TCP" && cols[1].ends_with(&suffix) && cols[3] == "LISTENING" {
            if let Ok(pid) = cols[4].parse::<u32>() {
                if pid != std::process::id() && !pids.contains(&pid) {
                    pids.push(pid);
                }
            }
        }
    }
    let mut killed_any = false;
    for pid in pids {
        if !is_python_process(pid) {
            eprintln!(
                "[kokyu] startup sweep: port {KERNEL_PORT} is held by pid {pid}, which is not Python; \
                 leaving it alone. The kernel cannot start until that port is free."
            );
            continue;
        }
        let ended = Command::new("taskkill")
            .args(["/PID", &pid.to_string(), "/F", "/T"])
            .creation_flags(CREATE_NO_WINDOW)
            .output()
            .map(|o| o.status.success())
            .unwrap_or(false);
        if ended {
            killed_any = true;
            eprintln!("[kokyu] startup sweep: ended a stale kernel (pid {pid})");
        } else {
            eprintln!("[kokyu] startup sweep: could not end the stale kernel (pid {pid}); end it in Task Manager");
        }
    }
    if killed_any {
        // Let the OS release the socket before the new kernel binds it.
        std::thread::sleep(Duration::from_millis(500));
    }
}

fn is_python_process(pid: u32) -> bool {
    Command::new("tasklist")
        .args(["/FI", &format!("PID eq {pid}"), "/FO", "CSV", "/NH"])
        .creation_flags(CREATE_NO_WINDOW)
        .output()
        .map(|o| {
            let text = String::from_utf8_lossy(&o.stdout).to_lowercase();
            text.contains("\"python.exe\"") || text.contains("\"pythonw.exe\"")
        })
        .unwrap_or(false)
}

/// Tray: Show/Hide and Quit.
fn build_tray(app: &tauri::App) -> tauri::Result<()> {
    let show_hide = MenuItem::with_id(app, "show_hide", "Show/Hide Kōkyū", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&show_hide, &quit])?;

    let tray = TrayIconBuilder::new()
        .icon(app.default_window_icon().unwrap().clone())
        .tooltip("Kōkyū")
        .menu(&menu)
        .on_menu_event(|app, event| match event.id().as_ref() {
            "show_hide" => {
                if let Some(window) = app.get_webview_window("main") {
                    let visible = window.is_visible().unwrap_or(true);
                    let _ = if visible { window.hide() } else { window.show().and_then(|_| window.set_focus()) };
                }
            }
            "quit" => {
                if let Some(kernel) = app.try_state::<KernelChild>() {
                    shut_down_kernel(&kernel.0);
                }
                app.exit(0)
            }
            _ => {}
        })
        .build(app)?;
    app.manage(TrayIconHandle(tray));
    Ok(())
}

/// Asks the kernel to shut down (POST /shutdown), so it saves the session's
/// memory and stops what it started, then waits up to 5 s (the kernel's own
/// bound) before ending it hard.
fn shut_down_kernel(kernel: &Arc<Mutex<Option<Child>>>) {
    request_kernel_shutdown();
    let deadline = Instant::now() + Duration::from_secs(5);
    loop {
        let exited = match kernel.lock() {
            Ok(mut slot) => slot.as_mut().map_or(true, |child| matches!(child.try_wait(), Ok(Some(_)))),
            Err(_) => break,
        };
        if exited || Instant::now() >= deadline {
            break;
        }
        std::thread::sleep(Duration::from_millis(200));
    }
    if let Ok(mut slot) = kernel.lock() {
        if let Some(child) = slot.as_mut() {
            let _ = child.kill(); // a no-op error if it already exited
        }
    }
}

/// One raw HTTP POST; the reply is not read. A connect failure (the kernel never
/// started, or already ended) is fine: the wait above covers it.
fn request_kernel_shutdown() {
    let addr: SocketAddr = KERNEL_ADDR.parse().expect("a fixed loopback address");
    let Ok(mut stream) = TcpStream::connect_timeout(&addr, Duration::from_millis(500)) else {
        return;
    };
    let _ = stream.write_all(
        b"POST /shutdown HTTP/1.1\r\nHost: 127.0.0.1:8780\r\nContent-Length: 0\r\nConnection: close\r\n\r\n",
    );
}
