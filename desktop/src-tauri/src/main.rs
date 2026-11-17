#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::{
    error::Error,
    fs::{self, OpenOptions},
    io::{self, BufRead, BufReader},
    os::windows::process::CommandExt,
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    ptr::{null, null_mut},
    sync::{mpsc, Mutex},
    thread,
    time::{Duration, Instant},
};
use tauri::{webview::NewWindowResponse, Manager, RunEvent, Url, WebviewUrl, WebviewWindowBuilder};
use windows_sys::Win32::UI::{
    Shell::ShellExecuteW,
    WindowsAndMessaging::{MessageBoxW, MB_ICONERROR, SW_SHOWNORMAL},
};

struct Backend(Child);

impl Drop for Backend {
    fn drop(&mut self) {
        // 关闭管道通知后端正常退出，给 SQLite 和定时任务留出收尾时间。
        drop(self.0.stdin.take());
        let deadline = Instant::now() + Duration::from_secs(8);
        while Instant::now() < deadline {
            match self.0.try_wait() {
                Ok(Some(_)) => return,
                Ok(None) => thread::sleep(Duration::from_millis(50)),
                Err(_) => break,
            }
        }
        let _ = self.0.kill();
        let _ = self.0.wait();
    }
}

fn start_backend(
    executable: &Path,
    home: &Path,
    log: &Path,
) -> Result<(Backend, Url), Box<dyn Error>> {
    let mut backend = Backend(
        Command::new(executable)
            .env("ZFUNDPILOT_HOME", home)
            .env("PYTHONUTF8", "1")
            .current_dir(home)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(OpenOptions::new().create(true).append(true).open(log)?)
            .creation_flags(0x08000000) // CREATE_NO_WINDOW
            .spawn()?,
    );
    let stdout = backend.0.stdout.take().expect("stdout is piped");
    let (sender, receiver) = mpsc::sync_channel(1);
    thread::spawn(move || {
        let mut line = String::new();
        let result = BufReader::new(stdout).read_line(&mut line).map(|_| line);
        let _ = sender.send(result);
    });

    let line = receiver.recv_timeout(Duration::from_secs(45))??;
    if let Some(message) = line.trim().strip_prefix("error:") {
        return Err(io::Error::other(message).into());
    }
    let url = Url::parse(line.trim()).map_err(|_| io::Error::other("后端退出或未返回就绪地址"))?;
    if url.scheme() != "http"
        || url.host_str() != Some("127.0.0.1")
        || !url.path().starts_with("/_desktop/")
    {
        return Err(io::Error::other("后端返回了无效的就绪地址").into());
    }
    Ok((backend, url))
}

fn open_main_window(app: &tauri::App, home: PathBuf) -> Result<(), Box<dyn Error>> {
    fs::create_dir_all(&home)?;
    let executable = app
        .path()
        .resource_dir()?
        .join("backend/zfundpilot-backend.exe");
    let log = home.join("backend.log");
    let (backend, url) = start_backend(&executable, &home, &log)
        .map_err(|error| io::Error::other(format!("{error}\n日志：{}", log.display())))?;
    let origin = url.origin();
    let app_url = url.join("/")?;
    WebviewWindowBuilder::new(app, "main", WebviewUrl::External(url))
        .title("ZFundPilot")
        .inner_size(1280.0, 850.0)
        .on_navigation(move |target| target.origin() == origin)
        .on_new_window(move |target, _features| {
            if is_external_web_url(&target, &app_url) {
                open_in_browser(&target);
            }
            NewWindowResponse::Deny
        })
        .build()?;
    app.manage(Mutex::new(Some(backend)));
    Ok(())
}

fn is_external_web_url(target: &Url, app_url: &Url) -> bool {
    matches!(target.scheme(), "http" | "https") && target.origin() != app_url.origin()
}

fn open_in_browser(target: &Url) {
    let url: Vec<u16> = target.as_str().encode_utf16().chain([0]).collect();
    let result = unsafe {
        ShellExecuteW(
            null_mut(),
            null(),
            url.as_ptr(),
            null(),
            null(),
            SW_SHOWNORMAL,
        )
    };
    if result as isize <= 32 {
        show_error("无法打开系统默认浏览器。请检查 Windows 中的默认浏览器设置。");
    }
}

fn show_error(message: &str) {
    let message: Vec<u16> = message.encode_utf16().chain([0]).collect();
    let title: Vec<u16> = "ZFundPilot\0".encode_utf16().collect();
    unsafe { MessageBoxW(null_mut(), message.as_ptr(), title.as_ptr(), MB_ICONERROR) };
}

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            let home = app.path().app_local_data_dir()?;
            if let Err(error) = open_main_window(app, home) {
                show_error(&format!("ZFundPilot 启动失败\n{error}"));
                app.handle().exit(1);
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("无法初始化 ZFundPilot 桌面应用")
        .run(|app, event| {
            if let RunEvent::Exit = event {
                if let Some(backend) = app.try_state::<Mutex<Option<Backend>>>() {
                    drop(backend.lock().expect("backend lock poisoned").take());
                }
            }
        });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn only_external_web_urls_open_in_the_browser() {
        let app_url = Url::parse("http://127.0.0.1:48753/").unwrap();
        for (address, allowed) in [
            ("https://github.com/Euzohn/ZFundPilot", true),
            ("http://example.org/", true),
            ("http://127.0.0.1:48753/_desktop/bootstrap", false),
            ("file:///C:/Windows/", false),
            ("ms-settings:privacy", false),
        ] {
            let target = Url::parse(address).unwrap();
            assert_eq!(is_external_web_url(&target, &app_url), allowed, "{address}");
        }
    }
}
