import Ionicons from "@react-native-vector-icons/ionicons";
import { useRouter } from "expo-router";
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
  const toast = useToast();
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [sent, setSent] = useState(false);
  const [resetToken, setResetToken] = useState("");

  const submit = async () => {
    if (!email || !email.includes("@")) return setErr("Please enter a valid email");
    setBusy(true);
    setErr("");
    try {
      const res = await api("/auth/forgot-password", { body: { email } });
      setSent(true);
      setResetToken(res.reset_token || "");
      toast("Password reset email sent");
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
            <T size={20} weight="700" center>Email Sent</T>
            <T center color={colors.muted}>We've sent a password reset link to {email}. Please check your inbox and follow the instructions.</T>
            {resetToken ? (
              <View style={{ gap: space.sm, alignItems: "center" }}>
                <T size={12} color={colors.brandTertiary} center>For testing: Click below to reset password</T>
                <Btn label="Reset Password" onPress={() => router.push({ pathname: "/reset-password", params: { token: resetToken } })} />
              </View>
            ) : null}
            <Btn variant="ghost" label="Back to Login" onPress={() => router.back()} />
          </View>
        ) : (
          <>
            <T center color={colors.muted}>Enter your email address and we'll send you a link to reset your password.</T>
            <Field label="Email" value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" />
            {err ? <T color={colors.error} weight="600">{err}</T> : null}
            <Btn label="Send Reset Link" onPress={submit} loading={busy} />
            <Btn variant="ghost" label="Back to Login" onPress={() => router.back()} />
          </>
        )}
      </KeyboardAwareScrollView>
    </View>
  );
}
