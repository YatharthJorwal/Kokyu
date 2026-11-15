// NOTE: this sandbox has no Rust toolchain, so this file was originally
// written against the Tauri v2 API from memory and unverified. Confirmed
// building and running successfully on the user's real machine as of a
// launch that included spawn_backend_processes, the tray icon/camera
// indicator code, and everything else through that point -- the file is
// no longer "unverified from memory," but new additions since then still
// start in that same unverified state until their own first real build.
// Newest additions, not yet through a real build: the Job Object
// (install_kill_on_close_job), the startup sweep (kill_stale_listeners /
// is_python_process), and the `gpt_sovits_still_alive` try_wait check in
// spawn_backend_processes.

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
    menu::{CheckMenuItem, Menu, MenuItem},
    tray::{TrayIcon, TrayIconBuilder},
    Emitter, Manager, WindowEvent,
};
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Shortcut, ShortcutState};

/// Embedded at compile time rather than read from disk at runtime -- same
/// "don't depend on a working-directory-relative path being right" reasoning
/// as everything else that's been machine-specific trouble in this file.
/// Swapped onto the tray via set_camera_indicator (see its own doc comment)
/// whenever the frontend's camera toggle is armed; swapped back to
/// `app.default_window_icon()` when it isn't. Needs the `image-png` Cargo
/// feature (Cargo.toml) for `Image::from_bytes` below to even compile.
const CAMERA_ACTIVE_TRAY_ICON: &[u8] = include_bytes!("../icons/tray-camera-active.png");

/// Handle to the tray icon itself, stored as Tauri-managed state (same
/// pattern as `ManagedChildren`) so `set_camera_indicator` can swap its
/// icon later -- `build_tray()`'s own `.build(app)?` call used to just
/// discard this.
struct TrayIconHandle(TrayIcon);

/// The tray menu's "Use API model" check item, kept as state so the frontend
/// can push the server's value back into it (`sync_cloud_toggle`). The item
/// itself toggles natively on click; this only makes the check state match
/// what the orchestrator actually accepted, including the "no key" case.
struct CloudToggleItem(CheckMenuItem<tauri::Wry>);

/// Frontend -> Rust: the orchestrator replied with the authoritative value for
/// the API-model switch; put the tray check mark where it says. A failed call
/// is silent on purpose -- a tray item out of step is cosmetic, and the next
/// settings message (or restart) corrects it.
#[tauri::command]
fn sync_cloud_toggle(app: tauri::AppHandle, enabled: bool) -> Result<(), String> {
    if let Some(item) = app.try_state::<CloudToggleItem>() {
        item.0.set_checked(enabled).map_err(|err| err.to_string())?;
    }
    Ok(())
}

/// No visible console window for a spawned child process. Same numeric
/// flag Windows' own CreateProcess API uses -- there's no named constant
/// for it in std, so it's a bare literal (0x08000000, CREATE_NO_WINDOW,
/// per the Win32 docs).
const CREATE_NO_WINDOW: u32 = 0x08000000;

/// Handles to every child process Yuri spawned itself (GPT-SoVITS, the
/// orchestrator), stored as Tauri-managed state so the tray menu's "quit"
/// handler can shut them down before actually exiting -- spawning them
/// hidden and then never cleaning them up would leave them running
/// invisibly in the background forever, which is worse than the old
/// visible-terminal setup, not better.
///
/// Each entry is labeled (not just a bare `Child`) so the quit handler can
/// tell which one is the orchestrator -- it's the only one with a
/// graceful-shutdown HTTP endpoint to try first (see
/// `graceful_shutdown_then_kill()`); GPT-SoVITS has no such thing and is
/// just killed outright, same as before.
struct ManagedChildren(Arc<Mutex<Vec<(String, Child)>>>);

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

/// Frontend -> Rust: save the API key for `provider` in the Windows Credential
/// Manager and hand it to the running kernel (FR-R-6, D-059). One key at a time:
/// any other provider's saved key is removed. Returns whether the kernel got it now.
/// Never returns the key, or any part of it.
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

/// Frontend -> Rust: remove the saved API key for `provider`, here and in the
/// running kernel. Removing a key that is not there is fine.
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

/// Exposed to the frontend for later phases (e.g. a keyboard shortcut or a
/// HUD button) even though only the tray menu drives it in Phase 1.
#[tauri::command]
fn toggle_click_through(window: tauri::WebviewWindow, ignore: bool) -> Result<(), String> {
    window
        .set_ignore_cursor_events(ignore)
        .map_err(|e| e.to_string())
}

/// **UNVERIFIED -- no Rust toolchain in the sandbox this was written in.**
/// Phase 5's camera indicator, per `docs/ARCHITECTURE.md`'s own spec for
/// `capture_camera()`: "a visible 'camera active' indicator (tray icon
/// state) whenever it's used, even though nothing is displayed back to the
/// user." Called from the frontend's camera module (src/camera.ts) the
/// instant `getUserMedia` actually grants a live stream (active=true) and
/// the instant that stream is stopped (active=false) -- tracks "is the
/// camera stream open," not literally "is a frame being read from it this
/// millisecond," which is both simpler and more honest: the OS's own
/// camera light works the same way (on for the whole time a stream is
/// open, not just per-frame).
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

/// Puts this process (and therefore every child it later spawns --
/// GPT-SoVITS, the orchestrator and the real interpreter the venv's
/// python.exe launcher stub spawns underneath it, WebView2's helpers) into
/// a Windows Job Object flagged KILL_ON_JOB_CLOSE. The OS itself then kills
/// every process in the job the instant this one dies, *for any reason*:
/// tray Quit, End Task from the taskbar, Ctrl+C on `npm run tauri dev`, a
/// crash, Task Manager. That is the whole point -- every fix before this one
/// (graceful_shutdown_then_kill, the orchestrator's PID-file takeover) only
/// helps on paths where this process gets to run its own code before dying,
/// and End Task / Ctrl+C are exactly the paths where it doesn't, which is
/// what left orphaned GPT-SoVITS instances squatting port 9880 across
/// launches on the user's real machine.
///
/// Same pattern the Tauri project itself uses in tauri-driver. Kept alive
/// with mem::forget rather than stored anywhere: the job's handle must stay
/// open for the whole life of the process (dropping it would *trigger* the
/// kill early), and the OS closing it at process exit is exactly the
/// behavior wanted. A failure here is logged and otherwise ignored -- the
/// graceful-quit path and the PID-file takeover still exist as before, this
/// is an additional safety net, not a replacement.
///
/// **UNVERIFIED on a real build** -- API confirmed against the win32job
/// docs and tauri-driver's own usage, but never compiled here.
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
        Ok(job) => {
            eprintln!(
                "[yuri] kill-on-close job object ACTIVE -- Windows will kill \
                 GPT-SoVITS and the orchestrator if Yuri dies for any reason \
                 (End Task, Ctrl+C, crash, tray Quit)."
            );
            std::mem::forget(job);
        }
        Err(e) => eprintln!(
            "[yuri] WARNING: couldn't set up the kill-on-close job object ({e}); \
             children may be orphaned if Yuri is closed via End Task or Ctrl+C \
             instead of tray Quit."
        ),
    }
}

pub fn run() {
    // Must happen before anything spawns a child -- processes only inherit
    // job membership from a parent that's already in the job.
    #[cfg(windows)]
    install_kill_on_close_job();

    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            toggle_click_through,
            set_camera_indicator,
            sync_cloud_toggle,
            set_api_key,
            delete_api_key
        ])
        .setup(|app| {
            let window = app
                .get_webview_window("main")
                .expect("main window must exist -- check the label in tauri.conf.json");

            // K1-00d: a normal app window, centred (the bottom-right widget
            // placement went with the widget window).
            let _ = window.center();
            build_tray(app)?;
            register_push_to_talk_hotkey(app)?;

            let managed_children: Arc<Mutex<Vec<(String, Child)>>> = Arc::new(Mutex::new(Vec::new()));
            let kernel_pipe = KernelPipe::default();
            spawn_backend_processes(managed_children.clone(), kernel_pipe.clone());
            app.manage(ManagedChildren(managed_children));
            app.manage(kernel_pipe);

            Ok(())
        })
        .on_window_event(|window, event| {
            // Yuri is meant to live in the tray, not get closed by accident.
            // The only real "quit" is the tray menu's Quit item.
            if let WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let _ = window.hide();
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running Yuri");
}

/// F9 push-to-talk: registered as an OS-level global shortcut, so it works
/// regardless of which window has focus (a game, a browser, whatever) --
/// unlike a plain keydown listener in the frontend, which only fires while
/// Yuri's own window is focused, defeating the point of an always-on-top
/// desktop companion you talk to while doing something else. Emits a
/// "hotkey-talk" event with "pressed"/"released" as the payload; the
/// frontend (src/mic.ts, wired up in src/main.ts) does the actual recording
/// start/stop, same as a mic-button click -- this function's only job is
/// turning a raw key event into that event.
fn register_push_to_talk_hotkey(app: &tauri::App) -> Result<(), Box<dyn std::error::Error>> {
    let window = app
        .get_webview_window("main")
        .expect("main window must exist -- check the label in tauri.conf.json");

    let push_to_talk = Shortcut::new(None, Code::F9);
    let shortcut_for_handler = push_to_talk.clone();

    app.handle().plugin(
        tauri_plugin_global_shortcut::Builder::new()
            .with_handler(move |_app, scut, event| {
                if scut != &shortcut_for_handler {
                    return;
                }
                let state = match event.state() {
                    ShortcutState::Pressed => "pressed",
                    ShortcutState::Released => "released",
                };
                let _ = window.emit("hotkey-talk", state);
            })
            .build(),
    )?;

    app.global_shortcut().register(push_to_talk)?;

    Ok(())
}

/// Starts the kernel as a hidden child, logging to logs/orchestrator.log (D-060).
/// Everything runs on its own thread so window creation never waits on it: the
/// stale-port sweep (netstat, tasklist) and the spawn. The kernel itself starts the
/// voice server later, after the window is up and the chat model has loaded, so
/// the two never load at the same time; this process's Job Object still ends it.
///
/// Working directories are relative to src-tauri/ (this binary's cwd under
/// `tauri dev`). Not verified for a packaged build (K1b).
fn spawn_backend_processes(children: Arc<Mutex<Vec<(String, Child)>>>, kernel_pipe: KernelPipe) {
    std::thread::spawn(move || {
        let logs_dir = PathBuf::from("../logs");
        let _ = std::fs::create_dir_all(&logs_dir);
        // Must run before the spawn, so the fresh kernel binds cleanly.
        kill_stale_listeners(8780, "kernel");

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
        spawn_logged("orchestrator", &mut cmd, &logs_dir.join("orchestrator.log"), &children);
        if let (Ok(mut children), Ok(mut pipe)) = (children.lock(), kernel_pipe.0.lock()) {
            if let Some((_, child)) = children.iter_mut().find(|(label, _)| label == "orchestrator") {
                *pipe = child.stdin.take();
            }
        }
    });
}

/// True only for Python interpreters -- the one kind of process the startup
/// sweep below is willing to kill. Yuri's own children (GPT-SoVITS's embedded
/// python.exe, the orchestrator's venv python.exe) are all Python, so this
/// is enough to clean up Yuri's own orphans without ever touching, say, a
/// browser or a game that happens to be sitting on the same port.
fn is_python_process(pid: u32) -> bool {
    let out = Command::new("tasklist")
        .args(["/FI", &format!("PID eq {pid}"), "/FO", "CSV", "/NH"])
        .creation_flags(CREATE_NO_WINDOW)
        .output();
    match out {
        Ok(o) => {
            let text = String::from_utf8_lossy(&o.stdout).to_lowercase();
            text.contains("\"python.exe\"") || text.contains("\"pythonw.exe\"")
        }
        Err(_) => false,
    }
}

/// **UNVERIFIED -- no Rust toolchain in the sandbox this was written in.**
/// Startup sweep: before spawning anything, kill any stale Python process
/// still LISTENING on `port` from a previous Yuri run. This is the safety
/// net behind the Job Object (install_kill_on_close_job): the Job Object
/// stops *new* orphans, but this also clears ones left by older builds, by
/// a Job Object that failed to install, or by anything else -- so a stale
/// GPT-SoVITS can never again silently squat port 9880 and make a fresh
/// launch fail to bind. Same manual steps the user had to do by hand
/// (`netstat -ano | findstr :9880`, `taskkill /PID <pid> /F`), automated,
/// with `/T` so a launcher stub's real-interpreter child dies with it.
/// Deliberately refuses to kill non-Python holders (see is_python_process)
/// and says so instead of failing silently.
fn kill_stale_listeners(port: u16, what: &str) {
    let output = match Command::new("netstat")
        .args(["-ano", "-p", "TCP"])
        .creation_flags(CREATE_NO_WINDOW)
        .output()
    {
        Ok(o) => o,
        Err(e) => {
            eprintln!(
                "[yuri] startup sweep: couldn't run netstat ({e}); not checking port {port} ({what})"
            );
            return;
        }
    };
    let text = String::from_utf8_lossy(&output.stdout);
    let suffix = format!(":{port}");
    let mut pids: Vec<u32> = Vec::new();
    for line in text.lines() {
        // Proto  Local Address  Foreign Address  State  PID
        let cols: Vec<&str> = line.split_whitespace().collect();
        if cols.len() >= 5 && cols[0] == "TCP" && cols[1].ends_with(&suffix) && cols[3] == "LISTENING"
        {
            if let Ok(pid) = cols[4].parse::<u32>() {
                if !pids.contains(&pid) {
                    pids.push(pid);
                }
            }
        }
    }

    let mut killed_any = false;
    for pid in pids {
        if pid == std::process::id() {
            continue;
        }
        if !is_python_process(pid) {
            eprintln!(
                "[yuri] startup sweep: port {port} ({what}) is held by pid {pid}, which isn't a \
                 Python process -- leaving it alone. Free that port yourself or the {what} \
                 won't be able to start."
            );
            continue;
        }
        let result = Command::new("taskkill")
            .args(["/PID", &pid.to_string(), "/F", "/T"])
            .creation_flags(CREATE_NO_WINDOW)
            .output();
        match result {
            Ok(o) if o.status.success() => {
                killed_any = true;
                eprintln!(
                    "[yuri] startup sweep: killed stale python process (pid {pid}) still \
                     listening on port {port} ({what}) from a previous run."
                );
            }
            _ => eprintln!(
                "[yuri] startup sweep: tried to kill stale python pid {pid} on port {port} \
                 ({what}) but taskkill failed -- kill it manually."
            ),
        }
    }
    if killed_any {
        // Give the OS a moment to actually release the socket so the fresh
        // process's bind doesn't race the dying one's.
        std::thread::sleep(Duration::from_millis(500));
    }
}

/// Spawns `command` hidden (no console window), with both stdout and
/// stderr going to `log_path`, and records the resulting Child (alongside
/// `label`, so the quit handler can tell processes apart -- see
/// ManagedChildren's doc comment) in `children` so it can be shut down on
/// quit. `command` should invoke the real interpreter directly, not
/// through a shell -- see the quit handler's comment for why.
fn spawn_logged(
    label: &str,
    command: &mut Command,
    log_path: &std::path::Path,
    children: &Arc<Mutex<Vec<(String, Child)>>>,
) {
    let stdout_file = match std::fs::File::create(log_path) {
        Ok(f) => f,
        Err(e) => {
            eprintln!("[yuri] couldn't open {}: {e}", log_path.display());
            return;
        }
    };
    let stderr_file = match stdout_file.try_clone() {
        Ok(f) => f,
        Err(e) => {
            eprintln!("[yuri] couldn't duplicate the log handle for {label}: {e}");
            return;
        }
    };

    match command
        .creation_flags(CREATE_NO_WINDOW)
        .stdout(Stdio::from(stdout_file))
        .stderr(Stdio::from(stderr_file))
        .spawn()
    {
        Ok(child) => {
            if let Ok(mut children) = children.lock() {
                children.push((label.to_string(), child));
            }
        }
        Err(e) => eprintln!("[yuri] failed to start {label}: {e}"),
    }
}

/// Tray icon + menu: Show/Hide, Toggle Click-through, Use API model, Quit.
fn build_tray(app: &tauri::App) -> tauri::Result<()> {
    let show_hide = MenuItem::with_id(app, "show_hide", "Show/Hide Yuri", true, None::<&str>)?;
    let click_through = MenuItem::with_id(
        app,
        "click_through",
        "Toggle Click-through",
        true,
        None::<&str>,
    )?;
    // Checkable: the OS flips the mark on click; the handler below only reports
    // the new state and the frontend asks the orchestrator to accept it. The
    // authoritative value comes back via `sync_cloud_toggle`, so a failed or
    // refused change (no AIROUTER_API_KEY, orchestrator down) snaps back.
    let use_api = CheckMenuItem::with_id(
        app,
        "use_api_model",
        "Use API model (cloud)",
        true,
        false,
        None::<&str>,
    )?;
    let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&show_hide, &click_through, &use_api, &quit])?;
    app.manage(CloudToggleItem(use_api));

    // Interior mutability instead of a mutable capture: on_menu_event's
    // closure is `Fn`, not `FnMut` (it may be invoked from more than one
    // call site), so a plain `let mut` captured by the closure won't compile.
    let click_through_state = Arc::new(AtomicBool::new(false));

    let tray = TrayIconBuilder::new()
        .icon(app.default_window_icon().unwrap().clone())
        .menu(&menu)
        .on_menu_event(move |app, event| {
            let Some(window) = app.get_webview_window("main") else {
                return;
            };
            match event.id().as_ref() {
                "show_hide" => {
                    let visible = window.is_visible().unwrap_or(true);
                    let _ = if visible { window.hide() } else { window.show() };
                }
                "click_through" => {
                    let now_ignoring = !click_through_state.load(Ordering::Relaxed);
                    click_through_state.store(now_ignoring, Ordering::Relaxed);
                    let _ = window.set_ignore_cursor_events(now_ignoring);
                }
                "use_api_model" => {
                    // Report only. Whether cloud is actually usable (a key, a
                    // catalog, budget) is the orchestrator's call, so the real
                    // state comes back through sync_cloud_toggle.
                    let checked = app
                        .try_state::<CloudToggleItem>()
                        .map(|item| item.0.is_checked().unwrap_or(false))
                        .unwrap_or(false);
                    let _ = app.emit("yuri://use-api-model", checked);
                }
                "quit" => {
                    // Try a graceful shutdown first, falling back to a
                    // hard kill for anything still alive after a bounded
                    // wait -- see graceful_shutdown_then_kill()'s own doc
                    // comment for why child.kill() alone isn't enough
                    // anymore (it was silently losing Phase 3 memory
                    // consolidation on every quit, found while answering
                    // the user's own "what's the right way to close this"
                    // question -- see docs/DECISIONS.md).
                    if let Some(state) = app.try_state::<ManagedChildren>() {
                        graceful_shutdown_then_kill(&state.0);
                    }
                    app.exit(0)
                }
                _ => {}
            }
        })
        .build(app)?;

    app.manage(TrayIconHandle(tray));

    Ok(())
}

/// **UNVERIFIED -- no Rust toolchain in the sandbox this was written in.**
/// Written as carefully as the rest of this file, but treat with the same
/// suspicion the global-shortcut block started in before its one real
/// E0277 fix on first compile (see docs/DECISIONS.md) -- this is new code
/// of a similar kind, and there's a real chance something here needs a
/// small fix too on your first `cargo build`.
///
/// Tries a graceful shutdown of the orchestrator first -- a fire-and-
/// forget POST to its own `/shutdown` endpoint (see
/// KASANE/app.py's `shutdown_endpoint()` docstring) -- because
/// `child.kill()` alone (`TerminateProcess` on Windows) gives Python's
/// own `finally` block, and therefore Phase 3's `consolidate_session()`,
/// no chance to run at all. Every quit was silently losing that
/// session's memory before this existed.
///
/// Falls back to a hard `.kill()` for anything still alive after a
/// bounded wait, regardless of label -- GPT-SoVITS has no graceful
/// shutdown path of its own (nothing here asks it for one), and the
/// orchestrator itself falls back to this too if it doesn't finish
/// tearing down in time -- so quitting never hangs waiting on either one,
/// and never leaves an orphaned process behind either way.
fn graceful_shutdown_then_kill(children: &Arc<Mutex<Vec<(String, Child)>>>) {
    request_orchestrator_shutdown();

    // Matched to KASANE/app.py's own ~5s bounded wait for its
    // connections to finish tearing down -- if that window's ever too
    // short for a slow consolidation LLM call, it's a mismatch to widen
    // on both sides together, not just one.
    let deadline = Instant::now() + Duration::from_secs(5);
    loop {
        let all_exited = match children.lock() {
            Ok(mut children) => children
                .iter_mut()
                .all(|(_label, child)| matches!(child.try_wait(), Ok(Some(_)))),
            Err(_) => break,
        };
        if all_exited || Instant::now() >= deadline {
            break;
        }
        std::thread::sleep(Duration::from_millis(200));
    }

    // Whatever's still alive at this point (graceful shutdown didn't
    // finish in time, or it's GPT-SoVITS which never had a graceful path
    // to begin with) gets hard-killed here, same as the old unconditional
    // behavior. Calling .kill() on a process that already exited on its
    // own is a harmless no-op error on Windows, so there's no need to
    // re-check try_wait() here first -- just always attempt it.
    if let Ok(mut children) = children.lock() {
        for (_label, child) in children.iter_mut() {
            let _ = child.kill();
        }
    }
}

/// Fire-and-forget raw HTTP/1.1 POST to the orchestrator's `/shutdown`
/// endpoint -- a plain `TcpStream` write, not a new HTTP client
/// dependency (see Cargo.toml -- nothing like `reqwest`/`ureq` is pulled
/// in anywhere else in this project either, and one fire-and-forget POST
/// with an empty body isn't worth adding one for). Doesn't wait for or
/// read the response -- graceful_shutdown_then_kill()'s own poll loop is
/// what actually waits on the *result* of this; this function only needs
/// the request to actually reach the server.
///
/// A connect failure (orchestrator already dead, port not open yet, or
/// launcher.local.txt/venv not set up so it never started at all) is
/// expected and handled fine by the poll-then-kill fallback above either
/// way -- silently returning here on any connect error is deliberate, not
/// an oversight.
fn request_orchestrator_shutdown() {
    let addr: SocketAddr = "127.0.0.1:8780"
        .parse()
        .expect("hardcoded loopback address is always valid");
    let Ok(mut stream) = TcpStream::connect_timeout(&addr, Duration::from_millis(500)) else {
        return;
    };
    let _ = stream.write_all(
        b"POST /shutdown HTTP/1.1\r\nHost: 127.0.0.1:8780\r\nContent-Length: 0\r\nConnection: close\r\n\r\n",
    );
}
