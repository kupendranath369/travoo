import Ionicons from "@react-native-vector-icons/ionicons";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { useRouter } from "expo-router";
import React, { useState } from "react";
import { Pressable, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { useAuth } from "@/src/auth";
import { Logo } from "@/src/components/Logo";
import { PhoneOtp } from "@/src/components/PhoneOtp";
import { Btn, Field, T, radius, space } from "@/src/components/ui";
import { useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

const HERO = "https://images.unsplash.com/photo-1614846623957-165ceffbf8d0?w=1200&q=70";

export default function AuthScreen() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t, lang } = useI18n();
  const { login, googleLogin, signInWith } = useAuth();
  const router = useRouter();
  const [mode, setMode] = useState<"phone" | "email">("phone");
  const [f, setF] = useState({ email: "", password: "", name: "" });
  const [ticket, setTicket] = useState<{ ticket: string; phone: string } | null>(null);
  const [accountType, setAccountType] = useState<"passenger" | "driver">("passenger");
  const [consent, setConsent] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (v: string) => setF((p) => ({ ...p, [k]: v }));

  const onOtp = async (r: any) => {
    if (r.needs_profile) return setTicket({ ticket: r.ticket, phone: r.phone });
    await signInWith(r.token, r.user);
  };

  const submit = async () => {
    setErr("");
    setBusy(true);
    try {
      if (mode === "email") await login(f.email.trim(), f.password);
      else if (ticket) {
        if (f.name.trim().length < 2) throw new Error("Enter your full name");
        if (!consent) throw new Error(t("auth.consent_required"));
        const r = await api("/auth/otp/complete", { body: { ticket: ticket.ticket, name: f.name.trim(), account_type: accountType, language: lang, consent } });
        await signInWith(r.token, r.user);
        if (accountType === "driver") router.push("/driver");
      }
    } catch (e: any) {
      setErr(e.message);
    }
    setBusy(false);
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <KeyboardAwareScrollView bottomOffset={24} keyboardShouldPersistTaps="handled" contentContainerStyle={{ paddingBottom: insets.bottom + space.xl }}>
        <View style={{ height: 260 }}>
          <Image source={{ uri: HERO }} style={{ position: "absolute", width: "100%", height: "100%" }} contentFit="cover" />
          <LinearGradient colors={["rgba(7,59,130,0.2)", "rgba(7,59,130,0.85)"]} style={{ position: "absolute", width: "100%", height: "100%" }} />
          <View style={{ position: "absolute", top: insets.top + space.md, right: space.lg }}>
            <Pressable testID="auth-language-button" onPress={() => router.push("/language?from=profile")} style={{ flexDirection: "row", gap: 6, alignItems: "center", backgroundColor: "rgba(255,255,255,0.2)", paddingHorizontal: space.md, height: 36, borderRadius: radius.pill }}>
              <Ionicons name="language" size={16} color={colors.onBrand} />
              <T size={13} weight="600" color={colors.onBrand}>{t("profile.language")}</T>
            </Pressable>
          </View>
          <View style={{ position: "absolute", bottom: space.xl, left: space.lg, right: space.lg, gap: space.sm }}>
            <View style={{ backgroundColor: colors.surfaceSecondary, alignSelf: "flex-start", padding: space.sm, borderRadius: radius.md }}>
              <Logo size={36} />
            </View>
            <T size={24} weight="800" color={colors.onBrand}>{t("home.hero")}</T>
          </View>
        </View>
        <View style={{ padding: space.lg, gap: space.md, marginTop: -space.md, backgroundColor: colors.surface, borderTopLeftRadius: radius.lg, borderTopRightRadius: radius.lg }}>
          <T size={22} weight="800">{ticket ? "Create your account" : mode === "phone" ? "Sign in or register with mobile" : "Sign in with email"}</T>
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
              <Field testID="auth-email-input" label={t("auth.email")} value={f.email} onChangeText={set("email")} autoCapitalize="none" keyboardType="email-address" />
              <Field testID="auth-password-input" label={t("auth.password")} value={f.password} onChangeText={set("password")} secureTextEntry />
              {err ? <T testID="auth-error" color={colors.error} weight="600">{err}</T> : null}
              <Btn testID="auth-submit-button" label={t("auth.login")} onPress={submit} loading={busy} />
              <Pressable testID="auth-forgot-password-link" onPress={() => router.push("/forgot-password")} style={{ padding: space.sm }}>
                <T center weight="700" color={colors.brandPrimary}>Forgot Password?</T>
              </Pressable>
              <T size={12} color={colors.muted} center>New accounts are created with a mobile number. Existing email users: after signing in, verify your number in Profile to use OTP next time.</T>
            </>
          ) : null}
          <View style={{ flexDirection: "row", alignItems: "center", gap: space.md }}>
            <View style={{ flex: 1, height: 1, backgroundColor: colors.border }} />
            <T color={colors.muted}>{t("auth.or")}</T>
            <View style={{ flex: 1, height: 1, backgroundColor: colors.border }} />
          </View>
          <Btn testID="auth-google-button" variant="outline" icon="logo-google" label={t("auth.google")} onPress={googleLogin} />
          <Pressable testID="auth-toggle-mode" onPress={() => { setErr(""); setTicket(null); setMode(mode === "phone" ? "email" : "phone"); }} style={{ padding: space.md }}>
            <T center weight="700" color={colors.brandPrimary}>{mode === "phone" ? "Existing account? Sign in with email" : "Use mobile number & OTP"}</T>
          </Pressable>
        </View>
      </KeyboardAwareScrollView>
    </View>
  );
}
