import Ionicons from "@react-native-vector-icons/ionicons";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { useRouter } from "expo-router";
import React, { useState } from "react";
import { Pressable, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useAuth } from "@/src/auth";
import { Logo } from "@/src/components/Logo";
import { Btn, Field, T, radius, space } from "@/src/components/ui";
import { useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

const HERO = "https://images.unsplash.com/photo-1614846623957-165ceffbf8d0?w=1200&q=70";

export default function AuthScreen() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t, lang } = useI18n();
  const { login, register, googleLogin } = useAuth();
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [f, setF] = useState({ email: "", password: "", name: "", phone: "" });
  const [consent, setConsent] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (v: string) => setF((p) => ({ ...p, [k]: v }));

  const submit = async () => {
    setErr("");
    if (mode === "register" && !consent) return setErr(t("auth.consent_required"));
    setBusy(true);
    try {
      if (mode === "login") await login(f.email.trim(), f.password);
      else await register({ email: f.email.trim(), password: f.password, name: f.name.trim(), phone: f.phone.trim(), language: lang, consent });
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
          <T size={22} weight="800">{mode === "login" ? t("auth.login") : t("auth.register")}</T>
          {mode === "register" ? (
            <>
              <Field testID="auth-name-input" label={t("auth.name")} value={f.name} onChangeText={set("name")} />
              <Field testID="auth-phone-input" label={t("auth.phone")} value={f.phone} onChangeText={set("phone")} keyboardType="phone-pad" maxLength={10} />
            </>
          ) : null}
          <Field testID="auth-email-input" label={t("auth.email")} value={f.email} onChangeText={set("email")} autoCapitalize="none" keyboardType="email-address" />
          <Field testID="auth-password-input" label={t("auth.password")} value={f.password} onChangeText={set("password")} secureTextEntry />
          {mode === "register" ? (
            <Pressable testID="auth-consent-checkbox" onPress={() => setConsent(!consent)} style={{ flexDirection: "row", gap: space.sm, alignItems: "flex-start" }}>
              <Ionicons name={consent ? "checkbox" : "square-outline"} size={22} color={colors.brandPrimary} />
              <T size={13} style={{ flex: 1 }}>
                {t("auth.consent")}{" "}
                <T size={13} weight="700" color={colors.brandPrimary} onPress={() => router.push("/legal?doc=terms")}>{t("legal.terms")}</T>
              </T>
            </Pressable>
          ) : null}
          {err ? <T testID="auth-error" color={colors.error} weight="600">{err}</T> : null}
          <Btn testID="auth-submit-button" label={mode === "login" ? t("auth.login") : t("auth.register")} onPress={submit} loading={busy} />
          <View style={{ flexDirection: "row", alignItems: "center", gap: space.md }}>
            <View style={{ flex: 1, height: 1, backgroundColor: colors.border }} />
            <T color={colors.muted}>{t("auth.or")}</T>
            <View style={{ flex: 1, height: 1, backgroundColor: colors.border }} />
          </View>
          <Btn testID="auth-google-button" variant="outline" icon="logo-google" label={t("auth.google")} onPress={googleLogin} />
          <Pressable testID="auth-toggle-mode" onPress={() => { setErr(""); setMode(mode === "login" ? "register" : "login"); }} style={{ padding: space.md }}>
            <T center weight="700" color={colors.brandPrimary}>{mode === "login" ? t("auth.no_account") : t("auth.have_account")}</T>
          </Pressable>
        </View>
      </KeyboardAwareScrollView>
    </View>
  );
}
