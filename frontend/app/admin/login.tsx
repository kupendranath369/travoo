import Ionicons from "@react-native-vector-icons/ionicons";
import { useRouter } from "expo-router";
import React, { useState } from "react";
import { Pressable, Switch, TextInput, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { API_BASE } from "@/src/api";
import { setAdminToken } from "@/src/adminApi";
import { Logo } from "@/src/components/Logo";
import { Btn, Card, T, radius, space } from "@/src/components/ui";
import { useTheme } from "@/src/theme";

export default function AdminLogin() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [remember, setRemember] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) return setErr("Enter a valid email address");
    if (!password) return setErr("Enter your password");
    setBusy(true);
    setErr("");
    try {
      const res = await fetch(`${API_BASE}/admin/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim().toLowerCase(), password, remember }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Sign-in failed. Please try again.");
      await setAdminToken(data.token, remember);
      setPassword("");
      router.replace(data.admin.must_change_password ? "/admin/change-password" : "/admin/dashboard");
    } catch (e: any) {
      setErr(e.message === "Failed to fetch" ? "Can't reach the server. Check your connection." : e.message);
    }
    setBusy(false);
  };

  const input = { flex: 1, minHeight: 48, color: colors.onSurface, fontSize: 16 } as const;
  const box = { flexDirection: "row", alignItems: "center", gap: space.sm, borderWidth: 1, borderColor: colors.borderStrong, borderRadius: radius.md, paddingHorizontal: space.md, backgroundColor: colors.surfaceSecondary } as const;

  return (
    <View style={{ flex: 1, backgroundColor: colors.surfaceTertiary }}>
      <KeyboardAwareScrollView bottomOffset={24} keyboardShouldPersistTaps="handled"
        contentContainerStyle={{ flexGrow: 1, justifyContent: "center", alignItems: "center", padding: space.lg, paddingTop: insets.top + space.xl, paddingBottom: insets.bottom + space.xl }}>
        <Card style={{ width: "100%", maxWidth: 440, padding: space.xl, gap: space.md }}>
          <View style={{ alignItems: "center", gap: space.sm }}>
            <Logo size={44} />
            <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
              <Ionicons name="shield-checkmark" size={18} color={colors.brandPrimary} />
              <T testID="admin-login-heading" size={22} weight="800">Travoo Admin Portal</T>
            </View>
            <T size={13} color={colors.muted} center>Authorised staff only. All sign-ins are logged.</T>
          </View>

          <T size={13} weight="700">Email address</T>
          <View style={box}>
            <Ionicons name="mail-outline" size={18} color={colors.muted} />
            <TextInput testID="admin-login-email" style={input} value={email} onChangeText={setEmail} placeholder="admin@company.com" placeholderTextColor={colors.muted}
              autoCapitalize="none" autoComplete="email" keyboardType="email-address" textContentType="username" returnKeyType="next" />
          </View>

          <T size={13} weight="700">Password</T>
          <View style={box}>
            <Ionicons name="lock-closed-outline" size={18} color={colors.muted} />
            <TextInput testID="admin-login-password" style={input} value={password} onChangeText={setPassword} placeholder="Your password" placeholderTextColor={colors.muted}
              secureTextEntry={!show} autoCapitalize="none" autoComplete="password" textContentType="password" returnKeyType="go" onSubmitEditing={submit} />
            <Pressable testID="admin-login-toggle-password" hitSlop={12} onPress={() => setShow(!show)} accessibilityLabel={show ? "Hide password" : "Show password"}>
              <Ionicons name={show ? "eye-off-outline" : "eye-outline"} size={20} color={colors.muted} />
            </Pressable>
          </View>

          <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: space.sm }}>
              <Switch testID="admin-login-remember" value={remember} onValueChange={setRemember} trackColor={{ true: colors.brandPrimary, false: colors.border }} />
              <T size={13}>Remember me (7 days)</T>
            </View>
            <Pressable testID="admin-login-forgot" hitSlop={8} onPress={() => router.push({ pathname: "/forgot-password", params: { portal: "admin" } })}>
              <T size={13} weight="700" color={colors.brandPrimary}>Forgot password?</T>
            </Pressable>
          </View>

          {err ? <T testID="admin-login-error" color={colors.error} weight="600">{err}</T> : null}
          <Btn testID="admin-login-submit" icon="lock-closed" label="Secure Login" onPress={submit} loading={busy} />
          <Pressable testID="admin-login-back-app" onPress={() => router.replace("/")} style={{ alignItems: "center", padding: space.sm }}>
            <T size={12} color={colors.muted}>← Back to the Travoo app</T>
          </Pressable>
        </Card>
      </KeyboardAwareScrollView>
    </View>
  );
}
