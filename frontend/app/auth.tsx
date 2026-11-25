import Ionicons from "@react-native-vector-icons/ionicons";
import { useRouter } from "expo-router";
import React, { useState } from "react";
import { Pressable, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { useAuth } from "@/src/auth";
import { Wordmark } from "@/src/components/Brand";
import { PhoneOtp } from "@/src/components/PhoneOtp";
import { Btn, Field, T, radius, space } from "@/src/components/ui";
import { useOtpEnabled } from "@/src/useOtp";
import { useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";


export default function AuthScreen() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t, lang } = useI18n();
  const { login, register, googleLogin, signInWith } = useAuth();
  const router = useRouter();
  const otpOn = useOtpEnabled();
  const [mode, setMode] = useState<"phone" | "email">("email");
  const [showPw, setShowPw] = useState(false);
  const [f, setF] = useState({ email: "", password: "", name: "", phone: "" });
  const [ticket, setTicket] = useState<{ ticket: string; phone: string } | null>(null);
  const [accountType, setAccountType] = useState<"passenger" | "driver">("passenger");
  const [consent, setConsent] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [emailMode, setEmailMode] = useState<"login" | "register">("login");
  const set = (k: keyof typeof f) => (v: string) => setF((p) => ({ ...p, [k]: v }));

  const onOtp = async (r: any) => {
    if (r.needs_profile) return setTicket({ ticket: r.ticket, phone: r.phone });
    await signInWith(r.token, r.user);
  };

  const submit = async () => {
    setErr("");
    setBusy(true);
    try {
      if (mode === "email") {
        if (emailMode === "login") {
          await login(f.email.trim(), f.password);
        } else {
          if (f.name.trim().length < 2) throw new Error("Enter your full name");
          if (!consent) throw new Error(t("auth.consent_required"));
          await register({ email: f.email.trim(), password: f.password, name: f.name.trim(), phone: f.phone.replace(/\D/g, "").slice(-10), language: lang, consent });
        }
      } else if (ticket) {
        if (f.name.trim().length < 2) throw new Error("Enter your full name");
        if (!consent) throw new Error(t("auth.consent_required"));
        const r = await api("/auth/otp/complete", { body: { ticket: ticket.ticket, name: f.name.trim(), account_type: accountType, language: lang, consent } });
        await signInWith(r.token, r.user);
        if (accountType === "driver") router.push("/driver");
      } else if (mode === "phone" && !ticket) {
        // Temporarily disabled: Allow registration without OTP
        // TODO: Re-enable OTP verification when MSG91 API key is available
        if (f.name.trim().length < 2) throw new Error("Enter your full name");
        if (!consent) throw new Error(t("auth.consent_required"));
        // For now, redirect to email registration as OTP is disabled
        setMode("email");
        setEmailMode("register");
        setErr("Mobile OTP verification is temporarily disabled. Please register with email.");
      }
    } catch (e: any) {
      setErr(e.message);
    }
    setBusy(false);
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <KeyboardAwareScrollView bottomOffset={24} keyboardShouldPersistTaps="handled" contentContainerStyle={{ paddingBottom: insets.bottom + space.xl }}>
        <View style={{ paddingTop: insets.top + space.md, paddingHorizontal: space.lg, flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
          <View style={{ width: 40 }} />
          <Wordmark size={34} />
          <Pressable testID="auth-language-button" accessibilityLabel={t("profile.language")} onPress={() => router.push("/language?from=profile")} hitSlop={8}
            style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: colors.surfaceTertiary, alignItems: "center", justifyContent: "center" }}>
            <Ionicons name="language" size={18} color={colors.brand} />
          </Pressable>
        </View>
        <View style={{ padding: space.lg, gap: space.md, backgroundColor: colors.surface }}>
          <T size={24} weight="800" center>{ticket ? "Create your account" : mode === "phone" ? "Sign in or register with mobile" : emailMode === "register" ? "Create Your Account" : "Welcome back"}</T>
          {mode === "phone" && !ticket ? (
            <PhoneOtp testPrefix="auth-otp" onVerified={onOtp} />
          ) : null}
          {mode === "phone" && ticket ? (
            <>
              <T testID="auth-verified-phone" size={13} color={colors.success} weight="700">Verified {ticket.phone}</T>
              <Field testID="auth-name-input" label={t("auth.name")} value={f.name} onChangeText={set("name")} autoCapitalize="words" />
              <T weight="600">I want to</T>
              <View style={{ flexDirection: "row", gap: space.sm }}>
                {(["passenger", "driver"] as const).map((k) => (
                  <Pressable key={k} testID={`auth-type-${k}`} onPress={() => setAccountType(k)} style={{ flex: 1, minHeight: 56, borderRadius: radius.md, borderWidth: 1.5, borderColor: accountType === k ? colors.brandPrimary : colors.border, backgroundColor: accountType === k ? colors.brandSoft : colors.surfaceSecondary, alignItems: "center", justifyContent: "center", gap: 2, padding: space.sm }}>
                    <Ionicons name={k === "passenger" ? "person-outline" : "car-sport-outline"} size={20} color={accountType === k ? colors.brandPrimary : colors.muted} />
                    <T size={13} weight="700" color={accountType === k ? colors.brandPrimary : colors.onSurface}>{k === "passenger" ? "Travel as passenger" : "Drive & offer rides"}</T>
                  </Pressable>
                ))}
              </View>
              <Pressable testID="auth-consent-checkbox" onPress={() => setConsent(!consent)} style={{ flexDirection: "row", gap: space.sm, alignItems: "flex-start" }}>
                <Ionicons name={consent ? "checkbox" : "square-outline"} size={22} color={colors.brandPrimary} />
                <T size={13} style={{ flex: 1 }}>
                  {t("auth.consent")}{" "}
                  <T size={13} weight="700" color={colors.brandPrimary} onPress={() => router.push("/legal?doc=terms")}>{t("legal.terms")}</T>
                </T>
              </Pressable>
              {err ? <T testID="auth-error" color={colors.error} weight="600">{err}</T> : null}
              <Btn testID="auth-submit-button" label={t("auth.register")} onPress={submit} loading={busy} />
            </>
          ) : null}
          {mode === "email" ? (
            <>
              {emailMode === "register" ? <Field testID="auth-name-input" label={t("auth.name")} placeholder="Full Name" value={f.name} onChangeText={set("name")} autoCapitalize="words" /> : null}
              {emailMode === "register" ? <Field testID="auth-phone-input" label="Mobile Number (optional)" placeholder="10-digit mobile" value={f.phone} onChangeText={set("phone")} keyboardType="phone-pad" maxLength={14} /> : null}
              <Field testID="auth-email-input" label={t("auth.email")} value={f.email} onChangeText={set("email")} autoCapitalize="none" keyboardType="email-address" />
              <View>
                <Field testID="auth-password-input" label={t("auth.password")} value={f.password} onChangeText={set("password")} secureTextEntry={!showPw} autoCapitalize="none" />
                <Pressable testID="auth-password-toggle" accessibilityLabel={showPw ? "Hide password" : "Show password"} onPress={() => setShowPw(!showPw)} hitSlop={10}
                  style={{ position: "absolute", right: space.md, bottom: 14 }}>
                  <Ionicons name={showPw ? "eye-off-outline" : "eye-outline"} size={22} color={colors.muted} />
                </Pressable>
              </View>
              {emailMode === "register" ? (
                <>
                  <Pressable testID="auth-consent-checkbox" onPress={() => setConsent(!consent)} style={{ flexDirection: "row", gap: space.sm, alignItems: "flex-start" }}>
                    <Ionicons name={consent ? "checkbox" : "square-outline"} size={22} color={colors.brandPrimary} />
                    <T size={13} style={{ flex: 1 }}>
                      {t("auth.consent")}{" "}
                      <T size={13} weight="700" color={colors.brandPrimary} onPress={() => router.push("/legal?doc=terms")}>{t("legal.terms")}</T>
                    </T>
                  </Pressable>
                </>
              ) : null}
              {err ? <T testID="auth-error" color={colors.error} weight="600">{err}</T> : null}
              <Btn testID="auth-submit-button" icon="arrow-forward" label={emailMode === "register" ? t("auth.register") : t("auth.login")} onPress={submit} loading={busy} />
              {emailMode === "login" ? (
                <>
                  <Pressable testID="auth-forgot-password-link" onPress={() => router.push("/forgot-password")} style={{ padding: space.sm }}>
                    <T center weight="700" color={colors.brandPrimary}>Forgot Password?</T>
                  </Pressable>
                  <Pressable testID="auth-register-link" onPress={() => { setErr(""); setEmailMode("register"); }} style={{ padding: space.sm }}>
                    <T center weight="700" color={colors.brandPrimary}>{"Don't have an account? Register with email"}</T>
                  </Pressable>
                </>
              ) : (
                <Pressable testID="auth-login-link" onPress={() => { setErr(""); setEmailMode("login"); }} style={{ padding: space.sm }}>
                  <T center weight="700" color={colors.brandPrimary}>Already have an account? Sign in with email</T>
                </Pressable>
              )}
            </>
          ) : null}
          <View style={{ flexDirection: "row", alignItems: "center", gap: space.md }}>
            <View style={{ flex: 1, height: 1, backgroundColor: colors.border }} />
            <T color={colors.muted}>{t("auth.or")}</T>
            <View style={{ flex: 1, height: 1, backgroundColor: colors.border }} />
          </View>
          <Btn testID="auth-google-button" variant="outline" icon="logo-google" label={t("auth.google")} onPress={googleLogin} />
          {otpOn ? (
            <Pressable testID="auth-toggle-mode" onPress={() => { setErr(""); setTicket(null); setEmailMode("login"); setMode(mode === "phone" ? "email" : "phone"); }} style={{ padding: space.md }}>
              <T center weight="700" color={colors.brandPrimary}>{mode === "phone" ? "Use email instead" : "Use mobile number & OTP"}</T>
            </Pressable>
          ) : null}
        </View>
      </KeyboardAwareScrollView>
    </View>
  );
}
