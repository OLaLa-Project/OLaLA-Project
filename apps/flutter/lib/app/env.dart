enum AppEnvironment {
  dev,
  beta,
  prod,
}

class AppEnv {
  static const String _rawEnv = String.fromEnvironment(
    'APP_ENV',
    defaultValue: 'prod',
  );

  static const String _apiBaseOverride = String.fromEnvironment(
    'API_BASE',
    defaultValue: '',
  );

  static const String _wsBaseOverride = String.fromEnvironment(
    'WS_BASE',
    defaultValue: '',
  );

  static AppEnvironment get environment {
    switch (_rawEnv.toLowerCase()) {
      case 'dev':
        return AppEnvironment.dev;
      case 'beta':
        return AppEnvironment.beta;
      case 'prod':
      default:
        return AppEnvironment.prod;
    }
  }

  static String get environmentName {
    switch (environment) {
      case AppEnvironment.dev:
        return 'dev';
      case AppEnvironment.beta:
        return 'beta';
      case AppEnvironment.prod:
        return 'prod';
    }
  }

  static String get apiBase {
    if (_apiBaseOverride.isNotEmpty) {
      return _trimTrailingSlash(_apiBaseOverride);
    }

    switch (environment) {
      case AppEnvironment.dev:
        return 'http://127.0.0.1:8080/v1';
      case AppEnvironment.beta:
        return 'https://beta-api.olala.com/v1';
      case AppEnvironment.prod:
        return 'https://api.olala.com/v1';
    }
  }

  static String get wsBase {
    if (_wsBaseOverride.isNotEmpty) {
      return _trimTrailingSlash(_wsBaseOverride);
    }

    if (apiBase.startsWith('https://')) {
      return apiBase.replaceFirst('https://', 'wss://');
    }
    if (apiBase.startsWith('http://')) {
      return apiBase.replaceFirst('http://', 'ws://');
    }

    return 'wss://api.olala.com/v1';
  }

  static String _trimTrailingSlash(String value) {
    if (value.endsWith('/')) {
      return value.substring(0, value.length - 1);
    }
    return value;
  }
}
