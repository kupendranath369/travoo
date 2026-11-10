import { useRouter } from "expo-router";
import React, { useState } from "react";
import { View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { adminApi, adminLogout } from "@/src/adminApi";
import { Btn, Card, Field, T, space } from "@/src/components/ui";
import { useTheme } from "@/src/theme";

/** Forced on first sign-in: the bootstrap password from the server environment must be replaced. */
export default function AdminChangePassword() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const router = useRouter();
  const [cur, setCur] = useState("");
  const [p1, setP1] = useState("");
  const [p2, setP2] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    if (p1.length < 10 || !/[a-z]/.test(p1) || !/[A-Z]/.test(p1) || !/\d/.test(p1)) return setErr("Use at least 10 characters with upper and lower case letters and a number");
    if (p1 !== p2) return setErr("The new passwords do not match");
    setBusy(true);
    setErr("");
    try {
      await adminApi("/admin/auth/change-password", { body: { current_password: cur, new_password: p1 } });
      router.replace("/admin/dashboard");
    } catch (e: any) {
      setErr(e.message);
    }
    setBusy(false);
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surfaceTertiary }}>
      <KeyboardAwareScrollView bottomOffset={24} keyboardShouldPersistTaps="handled"
        contentContainerStyle={{ flexGrow: 1, justifyContent: "center", alignItems: "center", padding: space.lg, paddingTop: insets.top + space.xl, paddingBottom: insets.bottom + space.xl }}>
        <Card style={{ width: "100%", maxWidth: 440, padding: space.xl, gap: space.md }}>
          <T testID="admin-change-password-title" size={20} weight="800">Set your admin password</T>
          <T size={13} color={colors.muted}>Choose a new password for the Admin Portal. Other signed-in admin devices will be signed out.</T>
          <Field testID="admin-cp-current" label="Current password" value={cur} onChangeText={setCur} secureTextEntry autoCapitalize="none" />
          <Field testID="admin-cp-new" label="New password" value={p1} onChangeText={setP1} secureTextEntry autoCapitalize="none" />
          <Field testID="admin-cp-confirm" label="Confirm new password" value={p2} onChangeText={setP2} secureTextEntry autoCapitalize="none" />
          {err ? <T testID="admin-cp-error" color={colors.error} weight="600">{err}</T> : null}
          <Btn testID="admin-cp-submit" label="Save password" onPress={submit} loading={busy} />
          <Btn testID="admin-cp-back" variant="ghost" label="Back to dashboard" onPress={() => router.replace("/admin/dashboard")} />
          <Btn testID="admin-cp-logout" variant="ghost" label="Log out" onPress={async () => { await adminLogout(); router.replace("/admin/login"); }} />
        </Card>
      </KeyboardAwareScrollView>
    </View>
  );
}
