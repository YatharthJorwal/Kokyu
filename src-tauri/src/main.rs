// No extra console window next to the app in release builds. Do not remove.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    kokyu_lib::run();
}
