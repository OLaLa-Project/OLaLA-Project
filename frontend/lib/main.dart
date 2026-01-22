import 'package:flutter/material.dart';
import 'screens/home_screen.dart';

void main() {
  runApp(const OLaLAApp());
}

class OLaLAApp extends StatelessWidget {
  const OLaLAApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'OLaLA MVP',
      theme: ThemeData(useMaterial3: true),
      home: const HomeScreen(),
    );
  }
}
