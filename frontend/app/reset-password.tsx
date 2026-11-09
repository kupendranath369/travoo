import Ionicons from "@react-native-vector-icons/ionicons";
import { useRouter, useLocalSearchParams } from "expo-router";
import React, { useState } from "react";
import { View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { useToast } from "@/src/components/toast";
import { Btn, Field, Header, T, space } from "@/src/components/ui";
import { useTheme } from "@/src/theme";

export default function ResetPasswordScreen() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const router = useRouter();
  const { token } = useLocalSearchParams();
  const toast = useToast();
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [success, setSuccess] = useState(false);

  const submit = async () => {
    if (password.length < 8) return setErr("Password must be at least 8 characters");
    if (password !== confirmPassword) return setErr("Passwords do not match");
    setBusy(true);
    setErr("");
    try {
      await api("/auth/reset-password", { body: { token: token as string, new_password: password } });
      setSuccess(true);
      toast("Password reset successfully");
    } catch (e: any) {
      setErr(e.message);
    }
    setBusy(false);
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <Header title="Reset Password" />
      <KeyboardAwareScrollView bottomOffset={24} keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: space.lg, gap: space.lg, paddingBottom: insets.bottom + space.xl }}>
        {success ? (
          <View style={{ gap: space.md, alignItems: "center", paddingVertical: space.xl }}>
            <Ionicons name="checkmark-circle" size={80} color={colors.success} />
            <T testID="reset-success-title" size={20} weight="700" center>Password Reset Successful</T>
            <T center color={colors.muted}>Your password has been reset successfully. You can now log in with your new password.</T>
            <Btn testID="reset-go-login-button" label="Go to Login" onPress={() => router.replace("/auth")} />
          </View>
        ) : (
          <>
            <T center color={colors.muted}>Enter your new password below.</T>
            <Field testID="reset-password-input" label="New Password" value={password} onChangeText={setPassword} secureTextEntry />
            <Field testID="reset-confirm-input" label="Confirm Password" value={confirmPassword} onChangeText={setConfirmPassword} secureTextEntry />
            {err ? <T testID="reset-error" color={colors.error} weight="700">{err}</T> : null}
            <Btn testID="reset-submit-button" label="Reset Password" onPress={submit} loading={busy} />
            <Btn testID="reset-back-button" variant="ghost" label="Back to Login" onPress={() => router.replace("/auth")} />
          </>
        )}
      </KeyboardAwareScrollView>
    </View>
  );
}
