// 金水授权系统 — 固定激活码，免费分享
// 激活码：B站：金水1987（兼容旧版 SHA256 格式）

use sha2::{Sha256, Digest};

const VALID_CODE: &str = "B站：金水1987";

/// 验证用户输入的激活码
/// 支持两种格式：
/// 1. 明文 "B站：金水1987"（新格式）
/// 2. SHA256("B站：金水1987") 的 hex 值（旧版兼容）
pub fn verify_license(user_code: &str) -> bool {
    let input = user_code.trim();

    // 直接匹配明文
    if input == VALID_CODE {
        return true;
    }

    // 兼容旧版：验证是否等于 SHA256("B站：金水1987")
    let mut hasher = Sha256::new();
    hasher.update(VALID_CODE.as_bytes());
    let expected_hash = hex::encode(hasher.finalize());

    input == expected_hash
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_verify_direct() {
        assert!(verify_license("B站：金水1987"));
    }

    #[test]
    fn test_verify_hashed() {
        let mut hasher = Sha256::new();
        hasher.update(VALID_CODE.as_bytes());
        let hash = hex::encode(hasher.finalize());
        assert!(verify_license(&hash));
    }

    #[test]
    fn test_verify_invalid() {
        assert!(!verify_license("fake-key"));
        assert!(!verify_license(""));
    }
}
