import 'package:shared_preferences/shared_preferences.dart';
import '../../features/issue_chat/models/chat_user.dart';

/// 로컬 저장소 관리
class LocalStorage {
  static const _keyFirstLaunch = 'first_launch';
  static const _keyOnboardingCompleted = 'onboarding_completed';
  static const _keyCoachCompleted = 'coach_completed';
  static const _keyDarkMode = 'dark_mode';

  // 익명 사용자 관련 키
  static const _keyAnonymousUserId = 'anonymous_user_id';
  static const _keyAnonymousUserNickname = 'anonymous_user_nickname';
  static const _keyAnonymousUserColor = 'anonymous_user_color';

  /// 첫 실행 여부 확인
  static Future<bool> isFirstLaunch() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_keyFirstLaunch) ?? true;
  }

  /// 첫 실행 완료 표시
  static Future<void> setFirstLaunchCompleted() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_keyFirstLaunch, false);
  }

  /// Onboarding 완료 여부 확인
  static Future<bool> isOnboardingCompleted() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_keyOnboardingCompleted) ?? false;
  }

  /// Onboarding 완료 표시
  static Future<void> setOnboardingCompleted() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_keyOnboardingCompleted, true);
  }

  /// Coach 완료 여부 확인
  static Future<bool> isCoachCompleted() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_keyCoachCompleted) ?? false;
  }

  /// Coach 완료 표시
  static Future<void> setCoachCompleted() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_keyCoachCompleted, true);
  }

  /// 다크 모드 설정 불러오기 (null이면 저장된 값 없음)
  static Future<bool?> getDarkMode() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_keyDarkMode);
  }

  /// 다크 모드 설정 저장
  static Future<void> setDarkMode(bool isDarkMode) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_keyDarkMode, isDarkMode);
  }

  /// 익명 사용자 저장
  static Future<void> saveAnonymousUser(ChatUser user) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_keyAnonymousUserId, user.id);
    await prefs.setString(_keyAnonymousUserNickname, user.nickname);
    await prefs.setString(_keyAnonymousUserColor, user.avatarColor);
  }

  /// 익명 사용자 불러오기
  static Future<ChatUser?> getAnonymousUser() async {
    final prefs = await SharedPreferences.getInstance();
    final id = prefs.getString(_keyAnonymousUserId);
    final nickname = prefs.getString(_keyAnonymousUserNickname);
    final color = prefs.getString(_keyAnonymousUserColor);

    if (id == null || nickname == null || color == null) {
      return null;
    }

    return ChatUser(
      id: id,
      nickname: nickname,
      avatarColor: color,
    );
  }

  /// 모든 데이터 초기화
  static Future<void> clearAll() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.clear();
  }
}
