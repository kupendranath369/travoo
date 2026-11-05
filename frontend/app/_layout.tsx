import { QueryClientProvider } from "@tanstack/react-query";
import { useFonts } from "expo-font";
import { Stack, useRouter, useSegments } from "expo-router";
import { StatusBar } from "expo-status-bar";
import React, { useEffect } from "react";
import { LogBox, StyleSheet, View } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { KeyboardProvider } from "react-native-keyboard-controller";

import { AuthProvider, useAuth } from "@/src/auth";
import { ErrorBoundary } from "@/src/components/error-boundary";
import { LogoFull } from "@/src/components/Logo";
import { ToastProvider } from "@/src/components/toast";
import { api } from "@/src/api";
import { I18nProvider, useI18n } from "@/src/i18n";
import { queryClient } from "@/src/query-client";
import { useTheme } from "@/src/theme";

LogBox.ignoreAllLogs(true);

const PUBLIC = new Set(["auth", "language", "legal"]);

function Gate() {
  const { user, loading } = useAuth();
  const { ready, chosen, rtl, lang } = useI18n();
  const segments = useSegments();
  const router = useRouter();
  const { colors } = useTheme();
  const top = segments[0] as string | undefined;

  useEffect(() => {
    if (loading || !ready) return;
    if (!chosen && top !== "language") router.replace("/language");
    else if (chosen && !user && !PUBLIC.has(top ?? "")) router.replace("/auth");
    else if (user && top === "auth") router.replace("/");
  }, [loading, ready, chosen, user, top, router]);

  // keep the server copy of the preferred language in sync (used for notifications)
  useEffect(() => {
    if (user && chosen && user.language !== lang) api("/me", { method: "PUT", body: { language: lang } }).catch(() => {});
  }, [user, lang, chosen]);

  if (loading || !ready)
    return (
      <View testID="splash-screen" style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.surface }}>
        <LogoFull width={200} />
      </View>
    );
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
