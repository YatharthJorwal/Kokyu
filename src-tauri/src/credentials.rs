//! End-user API keys in the Windows Credential Manager (FR-R-6, D-037, D-059; K1-08b).
//!
//! One generic credential per provider: target `Kokyu/api-key/<provider>`, user
//! name `Kokyu`, the key as UTF-8 bytes, kept for this Windows user on this machine.
//! A key never appears in an error: errors carry the Win32 code only.

use std::ffi::c_void;
use std::ptr;

use windows_sys::Win32::Foundation::{GetLastError, ERROR_NOT_FOUND, FILETIME};
use windows_sys::Win32::Security::Credentials::{
    CredDeleteW, CredEnumerateW, CredFree, CredReadW, CredWriteW, CREDENTIALW,
    CRED_MAX_CREDENTIAL_BLOB_SIZE, CRED_PERSIST_LOCAL_MACHINE, CRED_TYPE_GENERIC,
};

const PREFIX: &str = "Kokyu/api-key/";
const USER_NAME: &str = "Kokyu";
/// Windows' own cap for a generic credential (2560 bytes) is below our 4 KB one, so it wins.
const MAX_KEY_BYTES: usize = {
    let windows = CRED_MAX_CREDENTIAL_BLOB_SIZE as usize;
    if windows < 4096 {
        windows
    } else {
        4096
    }
};

/// Frees what the Credential Manager allocated, on every path out.
struct Allocated(*const c_void);

impl Drop for Allocated {
    fn drop(&mut self) {
        if !self.0.is_null() {
            unsafe { CredFree(self.0) };
        }
    }
}

fn wide(text: &str) -> Vec<u16> {
    text.encode_utf16().chain(std::iter::once(0)).collect()
}

fn from_wide(text: *const u16) -> String {
    if text.is_null() {
        return String::new();
    }
    let mut len = 0;
    unsafe {
        while *text.add(len) != 0 {
            len += 1;
        }
        String::from_utf16_lossy(std::slice::from_raw_parts(text, len))
    }
}

/// The kernel's rule for a provider id, `^[a-z][a-z0-9_]{0,31}$` (KASANE/provider_presets.py).
fn valid_provider(provider: &str) -> bool {
    (1..=32).contains(&provider.len())
        && provider.as_bytes()[0].is_ascii_lowercase()
        && provider.bytes().all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b == b'_')
}

/// A pasted key, tidied: surrounding space and quotes and a leading `Bearer ` go.
/// What is left must look like an API key, by the kernel's rule (shell_keys.valid_key):
/// 8 to 1024 printable ASCII characters, no spaces. The input is never echoed.
pub fn clean_key(raw: &str) -> Result<String, String> {
    let mut key = raw.trim().trim_matches(|c| c == '"' || c == '\'').trim();
    // `get`, not `[..7]`: a non-ASCII paste must be refused, not panic mid-character.
    if key.get(..7).is_some_and(|head| head.eq_ignore_ascii_case("bearer ")) {
        key = key[7..].trim();
    }
    if !(8..=1024).contains(&key.len()) || !key.bytes().all(|b| (0x21..=0x7e).contains(&b)) {
        return Err("that does not look like an API key: paste the whole key, with no spaces".into());
    }
    Ok(key.to_string())
}

/// The credential's target name. The rejected name is not echoed: a caller that
/// swapped its arguments would otherwise put the key in the error.
fn target(provider: &str) -> Result<Vec<u16>, String> {
    if valid_provider(provider) {
        Ok(wide(&format!("{PREFIX}{provider}")))
    } else {
        Err("invalid provider name: a lower-case letter, then a-z, 0-9 or _ (32 at most)".into())
    }
}

fn failed(action: &str, code: u32) -> String {
    format!("Windows Credential Manager could not {action} (error {code})")
}

fn last_error() -> u32 {
    unsafe { GetLastError() }
}

/// The stored key for `provider`, or `None` if there is none.
pub fn get(provider: &str) -> Result<Option<String>, String> {
    let name = target(provider)?;
    let mut cred: *mut CREDENTIALW = ptr::null_mut();
    if unsafe { CredReadW(name.as_ptr(), CRED_TYPE_GENERIC, 0, &mut cred) } == 0 {
        let code = last_error();
        return if code == ERROR_NOT_FOUND { Ok(None) } else { Err(failed("read the key", code)) };
    }
    let _free = Allocated(cred as *const c_void);
    let bytes = unsafe {
        let cred = &*cred;
        if cred.CredentialBlob.is_null() || cred.CredentialBlobSize == 0 {
            return Ok(None); // an empty entry is no key
        }
        std::slice::from_raw_parts(cred.CredentialBlob, cred.CredentialBlobSize as usize).to_vec()
    };
    decode(bytes).map(Some).ok_or_else(|| "the stored key is not readable text: save it again".into())
}

/// The key from a blob: UTF-8 as `set` writes it, or UTF-16LE as `cmdkey` and the
/// Credential Manager window write it (a NUL byte is how that shows). A key never
/// contains NUL, so any left after decoding means the blob is not a key.
fn decode(bytes: Vec<u8>) -> Option<String> {
    let text = if bytes.contains(&0) {
        if bytes.len() % 2 != 0 {
            return None;
        }
        let units: Vec<u16> = bytes.chunks_exact(2).map(|pair| u16::from_le_bytes([pair[0], pair[1]])).collect();
        String::from_utf16(&units).ok()?
    } else {
        String::from_utf8(bytes).ok()?
    };
    (!text.is_empty() && !text.contains('\0')).then_some(text)
}

/// Stores (or replaces) the key for `provider`.
pub fn set(provider: &str, key: &str) -> Result<(), String> {
    let mut name = target(provider)?;
    let blob = key.as_bytes();
    if blob.is_empty() {
        return Err("the key is empty".into());
    }
    if blob.contains(&0) {
        return Err("the key contains a NUL character".into());
    }
    if blob.len() > MAX_KEY_BYTES {
        return Err(format!("the key is longer than {MAX_KEY_BYTES} bytes"));
    }
    let mut user = wide(USER_NAME);
    let cred = CREDENTIALW {
        Flags: 0,
        Type: CRED_TYPE_GENERIC,
        TargetName: name.as_mut_ptr(),
        Comment: ptr::null_mut(),
        LastWritten: FILETIME { dwLowDateTime: 0, dwHighDateTime: 0 },
        CredentialBlobSize: blob.len() as u32,
        CredentialBlob: blob.as_ptr() as *mut u8, // read only: CredWriteW copies it
        Persist: CRED_PERSIST_LOCAL_MACHINE,
        AttributeCount: 0,
        Attributes: ptr::null_mut(),
        TargetAlias: ptr::null_mut(),
        UserName: user.as_mut_ptr(),
    };
    if unsafe { CredWriteW(&cred, 0) } == 0 {
        return Err(failed("save the key", last_error()));
    }
    Ok(())
}

/// Removes the key for `provider`. Removing a key that is not there is fine.
pub fn delete(provider: &str) -> Result<(), String> {
    let name = target(provider)?;
    if unsafe { CredDeleteW(name.as_ptr(), CRED_TYPE_GENERIC, 0) } == 0 {
        let code = last_error();
        if code != ERROR_NOT_FOUND {
            return Err(failed("delete the key", code));
        }
    }
    Ok(())
}

/// The providers that have a key stored, sorted. Names only, never keys.
pub fn list() -> Result<Vec<String>, String> {
    let filter = wide(&format!("{PREFIX}*"));
    let mut count: u32 = 0;
    let mut creds: *mut *mut CREDENTIALW = ptr::null_mut();
    if unsafe { CredEnumerateW(filter.as_ptr(), 0, &mut count, &mut creds) } == 0 {
        let code = last_error();
        return if code == ERROR_NOT_FOUND { Ok(Vec::new()) } else { Err(failed("list the keys", code)) };
    }
    let _free = Allocated(creds as *const c_void);
    let mut names = Vec::new();
    for index in 0..count as usize {
        let cred = unsafe { *creds.add(index) };
        if cred.is_null() {
            continue;
        }
        let (kind, blob_size, target) = unsafe { ((*cred).Type, (*cred).CredentialBlobSize, (*cred).TargetName) };
        // An empty entry is no key: `get` says None for it, so this list must not name it.
        if kind != CRED_TYPE_GENERIC || blob_size == 0 {
            continue;
        }
        let target = from_wide(target);
        // Target names are case-insensitive (`get("openai")` reads "Kokyu/OpenAI"),
        // so the name is compared, and returned, in lower case.
        let provider = match target.get(..PREFIX.len()) {
            Some(head) if head.eq_ignore_ascii_case(PREFIX) => target[PREFIX.len()..].to_ascii_lowercase(),
            _ => continue,
        };
        if valid_provider(&provider) {
            names.push(provider);
        }
    }
    names.sort();
    names.dedup();
    Ok(names)
}

/// Every saved key with its provider, for the kernel at spawn (FR-R-6).
pub fn all() -> Result<Vec<(String, String)>, String> {
    let mut keys = Vec::new();
    for provider in list()? {
        if let Some(key) = get(&provider)? {
            keys.push((provider, key));
        }
    }
    Ok(keys)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A target of its own per test, removed even when the test fails.
    struct Throwaway(String);

    impl Throwaway {
        fn new(tag: &str) -> Self {
            let name = format!("kokyu_test_{}_{tag}", std::process::id());
            assert!(valid_provider(&name), "test name too long: {name}");
            let _ = delete(&name);
            Throwaway(name)
        }
    }

    impl Drop for Throwaway {
        fn drop(&mut self) {
            let _ = delete(&self.0);
        }
    }

    /// Writes an entry the way other tools may: any target case, any blob.
    fn write_foreign(target_name: &str, blob: &[u8]) {
        let mut name = wide(target_name);
        let mut user = wide(USER_NAME);
        let cred = CREDENTIALW {
            Flags: 0,
            Type: CRED_TYPE_GENERIC,
            TargetName: name.as_mut_ptr(),
            Comment: ptr::null_mut(),
            LastWritten: FILETIME { dwLowDateTime: 0, dwHighDateTime: 0 },
            CredentialBlobSize: blob.len() as u32,
            CredentialBlob: if blob.is_empty() { ptr::null_mut() } else { blob.as_ptr() as *mut u8 },
            Persist: CRED_PERSIST_LOCAL_MACHINE,
            AttributeCount: 0,
            Attributes: ptr::null_mut(),
            TargetAlias: ptr::null_mut(),
            UserName: user.as_mut_ptr(),
        };
        assert_ne!(unsafe { CredWriteW(&cred, 0) }, 0, "CredWriteW failed: {}", last_error());
    }

    fn utf16le(text: &str) -> Vec<u8> {
        text.encode_utf16().flat_map(|unit| unit.to_le_bytes()).collect()
    }

    #[test]
    fn a_pasted_key_is_tidied_and_checked_without_echoing_it() {
        assert_eq!(clean_key("  sk-or-v1-abc123  ").unwrap(), "sk-or-v1-abc123");
        assert_eq!(clean_key("\"sk-or-v1-abc123\"").unwrap(), "sk-or-v1-abc123");
        assert_eq!(clean_key("Bearer sk-or-v1-abc123").unwrap(), "sk-or-v1-abc123");
        for bad in ["", "short", "sk-or v1-abc123", "sk-or-v1-abc\n123", "ключ-ключ-ключ", &"k".repeat(1025)] {
            let err = clean_key(bad).unwrap_err();
            assert!(!err.contains("sk-or") && !err.contains("kkkk"), "{err}");
        }
    }

    #[test]
    fn blobs_decode_from_utf8_or_the_utf16_windows_tools_write() {
        assert_eq!(decode(b"sk-abc".to_vec()).as_deref(), Some("sk-abc"));
        assert_eq!(decode(utf16le("sk-abc")).as_deref(), Some("sk-abc"));
        assert_eq!(decode(utf16le("sk-ü-1")).as_deref(), Some("sk-ü-1"));
        // shortcut: UTF-16 is recognised by its NUL bytes, which every ASCII key has;
        // an all non-Latin UTF-16 blob would read as garbage. API keys are ASCII.
        assert_eq!(decode(vec![b's', 0, b'k']), None); // odd length: not UTF-16
        assert_eq!(decode(utf16le("sk\0abc")), None); // a NUL inside the text is not a key
        assert_eq!(decode(vec![0xff, 0xfe, 0xfd]), None);
        assert_eq!(decode(Vec::new()), None);
    }

    #[test]
    #[ignore = "writes the real Credential Manager: cargo test -- --ignored"]
    fn an_entry_saved_by_windows_own_tools_reads_back_and_is_listed() {
        let p = Throwaway::new("mix");
        // what `cmdkey /generic:Kokyu/<NAME> /pass:...` leaves: any case, UTF-16LE blob
        write_foreign(&format!("{PREFIX}{}", p.0.to_ascii_uppercase()), &utf16le("sk-from-cmdkey"));
        assert_eq!(get(&p.0).unwrap().as_deref(), Some("sk-from-cmdkey"));
        assert!(list().unwrap().contains(&p.0), "{:?}", list());
        delete(&p.0).unwrap();
        assert!(!list().unwrap().contains(&p.0));
    }

    #[test]
    #[ignore = "writes the real Credential Manager: cargo test -- --ignored"]
    fn an_empty_entry_is_neither_a_key_nor_listed() {
        let p = Throwaway::new("empty");
        write_foreign(&format!("{PREFIX}{}", p.0), b"");
        assert_eq!(get(&p.0).unwrap(), None);
        assert!(!list().unwrap().contains(&p.0));
    }

    #[test]
    #[ignore = "writes the real Credential Manager: cargo test -- --ignored"]
    fn a_key_round_trips_and_can_be_replaced_and_deleted() {
        let p = Throwaway::new("rt");
        assert_eq!(get(&p.0).unwrap(), None);
        set(&p.0, "sk-first-0123456789").unwrap();
        assert_eq!(get(&p.0).unwrap().as_deref(), Some("sk-first-0123456789"));
        set(&p.0, "sk-second").unwrap();
        assert_eq!(get(&p.0).unwrap().as_deref(), Some("sk-second"));
        delete(&p.0).unwrap();
        assert_eq!(get(&p.0).unwrap(), None);
        delete(&p.0).unwrap(); // already gone: still fine
    }

    #[test]
    #[ignore = "writes the real Credential Manager: cargo test -- --ignored"]
    fn non_ascii_keys_survive_as_utf8() {
        let p = Throwaway::new("utf");
        set(&p.0, "ключ-🔑-key").unwrap();
        assert_eq!(get(&p.0).unwrap().as_deref(), Some("ключ-🔑-key"));
    }

    #[test]
    #[ignore = "writes the real Credential Manager: cargo test -- --ignored"]
    fn list_names_providers_and_never_keys() {
        let p = Throwaway::new("ls");
        set(&p.0, "sk-listed-secret").unwrap();
        let names = list().unwrap();
        assert!(names.contains(&p.0), "{names:?}");
        assert!(names.iter().all(|n| !n.contains("secret")));
        delete(&p.0).unwrap();
        assert!(!list().unwrap().contains(&p.0));
    }

    #[test]
    #[ignore = "writes the real Credential Manager: cargo test -- --ignored"]
    fn bad_provider_names_are_refused_without_echoing_them() {
        for bad in ["", "OpenRouter", "a/b", "a b", "kokyu*", "open-router", "1abc", &"a".repeat(33)] {
            let err = get(bad).unwrap_err();
            assert!(err.contains("invalid provider name"), "{err}");
            assert!(set(bad, "sk-x").is_err() && delete(bad).is_err());
        }
        // Arguments swapped by mistake: a real key (mixed case) is refused, not echoed.
        let swapped = set("sk-or-v1-ABCdef0123456789", "openrouter").unwrap_err();
        assert!(!swapped.contains("sk-or"), "{swapped}");
        assert!(valid_provider("open_router2") && valid_provider(&"a".repeat(32)));
    }

    #[test]
    #[ignore = "writes the real Credential Manager: cargo test -- --ignored"]
    fn empty_and_oversized_keys_are_refused_and_nothing_is_written() {
        let p = Throwaway::new("big");
        assert_eq!(set(&p.0, "").unwrap_err(), "the key is empty");
        assert_eq!(set(&p.0, "sk-a\0b").unwrap_err(), "the key contains a NUL character");
        let too_long = "x".repeat(MAX_KEY_BYTES + 1);
        let err = set(&p.0, &too_long).unwrap_err();
        assert!(err.contains("longer than 2560 bytes") && !err.contains("xxxx"), "{err}");
        assert_eq!(get(&p.0).unwrap(), None);
        set(&p.0, &"y".repeat(MAX_KEY_BYTES)).unwrap(); // the limit itself is fine
        assert_eq!(get(&p.0).unwrap().map(|k| k.len()), Some(MAX_KEY_BYTES));
    }
}
