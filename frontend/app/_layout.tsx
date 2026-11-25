import { QueryClientProvider } from "@tanstack/react-query";
import { useFonts } from "expo-font";
import { Stack, useRouter, useSegments } from "expo-router";
import { StatusBar } from "expo-status-bar";
import React, { useEffect, useState } from "react";
import { LogBox, StyleSheet, Text, View } from "react-native";
import Animated, { FadeIn, FadeOut } from "react-native-reanimated";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { KeyboardProvider } from "react-native-keyboard-controller";

import { AuthProvider, useAuth } from "@/src/auth";
import { ErrorBoundary } from "@/src/components/error-boundary";
import { BrandPin, IMG, Wordmark } from "@/src/components/Brand";
import { Image } from "expo-image";
import { ToastProvider } from "@/src/components/toast";
import { api } from "@/src/api";
import { I18nProvider, useI18n } from "@/src/i18n";
import { queryClient } from "@/src/query-client";
import { useTheme } from "@/src/theme";

LogBox.ignoreAllLogs(true);

const PUBLIC = new Set(["auth", "language", "legal", "forgot-password", "reset-password", "admin"]);

function Gate() {
  const { user, loading } = useAuth();
  const { ready, chosen, rtl, lang } = useI18n();
  const segments = useSegments();
  const router = useRouter();
  const { colors } = useTheme();
  const top = segments[0] as string | undefined;
  const [showSplash, setShowSplash] = useState(true);

  useEffect(() => {
    if (loading || !ready) return;
    if (!chosen && top !== "language" && top !== "admin") router.replace("/language");
    else if (chosen && !user && !PUBLIC.has(top ?? "")) router.replace("/auth");
    else if (user && user.mode_chosen === false && top !== "mode" && top !== "admin" && top !== "legal") router.replace("/mode");
    else if (user && top === "auth") router.replace("/");
  }, [loading, ready, chosen, user, top, router]);

  // keep the server copy of the preferred language in sync (used for notifications)
  useEffect(() => {
    if (user && chosen && user.language !== lang) api("/me", { method: "PUT", body: { language: lang } }).catch(() => {});
  }, [user, lang, chosen]);

  // Hide splash screen after auth/language is ready
  useEffect(() => {
    if (!loading && ready) {
      const timer = setTimeout(() => setShowSplash(false), 1500);
      return () => clearTimeout(timer);
    }
  }, [loading, ready]);

  if (showSplash) {
    return (
      <Animated.View entering={FadeIn.duration(600)} exiting={FadeOut.duration(600)} testID="splash-screen" style={{ flex: 1, backgroundColor: "#EAF5FB" }}>
        <Image source={{ uri: IMG.splash }} style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: "62%" }} contentFit="cover" />
        <View style={{ alignItems: "center", paddingTop: "22%", gap: 10 }}>
          <BrandPin size={64} />
          <Wordmark size={56} />
          <Text style={{ fontFamily: "PJS-SemiBold", fontSize: 15, color: "#14233A" }}>Your Travel. Your Driver. Your Way.</Text>
        </View>
      </Animated.View>
    );
  }

  return (
    <View style={{ flex: 1, direction: rtl ? "rtl" : "ltr" }}>
      <StatusBar style="dark" />
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.surface } }} />
    </View>
  );
}

export default function RootLayout() {
  const [fontsLoaded] = useFonts({
    "PJS-Regular": require("../assets/fonts/PJS-400.ttf"),
    "PJS-Medium": require("../assets/fonts/PJS-500.ttf"),
    "PJS-SemiBold": require("../assets/fonts/PJS-600.ttf"),
    "PJS-Bold": require("../assets/fonts/PJS-700.ttf"),
    "PJS-ExtraBold": require("../assets/fonts/PJS-800.ttf"),
  });
  if (!fontsLoaded) return null;
  return (
    <GestureHandlerRootView style={styles.root}>
      <ErrorBoundary>
        <QueryClientProvider client={queryClient}>
          <KeyboardProvider>
            <I18nProvider>
              <AuthProvider>
                <ToastProvider>
                  <Gate />
                </ToastProvider>
              </AuthProvider>
            </I18nProvider>
          </KeyboardProvider>
        </QueryClientProvider>
      </ErrorBoundary>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({ root: { flex: 1 } });
