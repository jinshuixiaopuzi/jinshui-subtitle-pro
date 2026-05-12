mod license;

use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize)]
pub struct LicenseStatus {
    pub activated: bool,
}

/// 获取激活状态
#[tauri::command]
fn get_license_status() -> LicenseStatus {
    let stored = std::fs::read_to_string("license.key").unwrap_or_default();
    let activated = license::verify_license(stored.trim());
    LicenseStatus { activated }
}

/// 验证并激活
#[tauri::command]
fn activate_license(code: String) -> Result<String, String> {
    if license::verify_license(&code) {
        std::fs::write("license.key", code.trim()).map_err(|e| e.to_string())?;
        Ok("激活成功！欢迎使用金水字幕 Pro".to_string())
    } else {
        Err("激活码无效！请检查后重试".to_string())
    }
}

/// 获取引擎可执行文件路径（生产模式 engine.exe，开发模式 python）
fn get_engine_cmd() -> (String, Vec<String>) {
    // 生产模式：查找打包好的 engine/engine.exe
    if let Ok(exe_path) = std::env::current_exe() {
        if let Some(parent) = exe_path.parent() {
            let bundled_engine = parent.join("engine").join("engine.exe");
            let _ = std::fs::write(
                parent.join("engine_startup.log"),
                format!("[get_engine_cmd] exe_path={}\n  checking: {}\n  exists={}\n",
                    exe_path.display(), bundled_engine.display(), bundled_engine.exists()),
            );
            if bundled_engine.exists() {
                return (bundled_engine.to_string_lossy().to_string(), vec![]);
            }
            let sibling_engine = parent.join("engine.exe");
            if sibling_engine.exists() {
                return (sibling_engine.to_string_lossy().to_string(), vec![]);
            }
        }
    }
    // 开发模式：使用 venv python
    ("venv/Scripts/python.exe".to_string(), vec!["api_server.py".to_string()])
}

/// 启动 Python 后端引擎
#[tauri::command]
fn start_engine() -> Result<String, String> {
    let (cmd, args) = get_engine_cmd();

    if !std::path::Path::new(&cmd).exists() {
        return Err(format!("引擎未找到: {}", cmd));
    }

    let child = std::process::Command::new(&cmd)
        .args(&args)
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .spawn()
        .map_err(|e| format!("启动引擎失败: {}", e))?;

    Ok(format!("引擎已启动 (PID: {})", child.id()))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            get_license_status,
            activate_license,
            start_engine,
        ])
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            } else {
                // 生产模式：自动启动 AI 引擎
                let (cmd, args) = get_engine_cmd();
                let exe_dir = std::env::current_exe().ok()
                    .and_then(|p| p.parent().map(|d| d.to_path_buf()))
                    .unwrap_or_default();
                let log_path = exe_dir.join("app_startup.log");
                let engine_log = exe_dir.join("engine_output.log");
                let mut log_entries: Vec<String> = vec![];
                log_entries.push(format!("app_startup: exe_dir={}", exe_dir.display()));
                log_entries.push(format!("engine_cmd={}, args={:?}", cmd, args));

                if std::path::Path::new(&cmd).exists() {
                    let spawn_result = match std::fs::File::create(&engine_log) {
                        Ok(f) => {
                            let f2 = f.try_clone().ok();
                            std::process::Command::new(&cmd)
                                .args(&args)
                                .stdout(std::process::Stdio::from(f))
                                .stderr(if let Some(fe) = f2 { std::process::Stdio::from(fe) } else { std::process::Stdio::null() })
                                .spawn()
                        }
                        Err(_) => {
                            std::process::Command::new(&cmd)
                                .args(&args)
                                .stdout(std::process::Stdio::null())
                                .stderr(std::process::Stdio::null())
                                .spawn()
                        }
                    };
                    match spawn_result {
                        Ok(child) => {
                            let msg = format!("引擎已启动 (PID: {}), cmd={}", child.id(), cmd);
                            log_entries.push(msg);
                            std::thread::spawn(move || {
                                let _ = child.wait_with_output();
                            });
                        }
                        Err(e) => {
                            let msg = format!("引擎启动失败: {}, cmd={}", e, cmd);
                            log_entries.push(msg);
                        }
                    }
                } else {
                    let msg = format!("引擎未找到: {}", cmd);
                    log_entries.push(msg);
                }
                let _ = std::fs::write(&log_path, log_entries.join("\n"));
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
