import Ionicons from "@react-native-vector-icons/ionicons";
import { useLocalSearchParams, useRouter } from "expo-router";
import React, { useState } from "react";
import { View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { useToast } from "@/src/components/toast";
import { Btn, Field, Header, T, space } from "@/src/components/ui";
import { useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

export default function ForgotPasswordScreen() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t } = useI18n();
  const router = useRouter();
  const { portal } = useLocalSearchParams<{ portal?: string }>();
  const back = () => (router.canGoBack() ? router.back() : router.replace(portal === "admin" ? "/admin/login" : "/auth"));
  const toast = useToast();
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [sent, setSent] = useState(false);

  const submit = async () => {
    if (!email || !email.includes("@")) return setErr("Please enter a valid email");
    setBusy(true);
    setErr("");
    try {
      await api("/auth/forgot-password", { body: { email: email.trim().toLowerCase(), portal: portal === "admin" ? "admin" : "app" } });
      setSent(true);
      toast("Check your inbox for the reset link");
    } catch (e: any) {
      setErr(e.message);
    }
    setBusy(false);
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <Header title="Forgot Password" />
      <KeyboardAwareScrollView bottomOffset={24} keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: space.lg, gap: space.lg, paddingBottom: insets.bottom + space.xl }}>
        {sent ? (
          <View style={{ gap: space.md, alignItems: "center", paddingVertical: space.xl }}>
            <Ionicons name="mail-open-outline" size={80} color={colors.success} />
            <T testID="forgot-sent-title" size={20} weight="700" center>Check your email</T>
            <T center color={colors.muted}>If an account exists for {email}, we&apos;ve sent a link to reset your password. It expires in 30 minutes. Check your spam folder too.</T>
            <Btn testID="forgot-resend-button" variant="outline" label="Send again" onPress={submit} loading={busy} />
            <Btn testID="forgot-back-button" variant="ghost" label="Back to Login" onPress={back} />
          </View>
        ) : (
          <>
            <T center color={colors.muted}>Enter your email address and we&apos;ll send you a link to reset your password.</T>
            <Field testID="forgot-email-input" label="Email" value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" />
            {err ? <T testID="forgot-error" color={colors.error} weight="600">{err}</T> : null}
            <Btn testID="forgot-submit-button" label="Send Reset Link" onPress={submit} loading={busy} />
            <Btn testID="forgot-cancel-button" variant="ghost" label="Back to Login" onPress={back} />
          </>
        )}
      </KeyboardAwareScrollView>
    </View>
  );
}
