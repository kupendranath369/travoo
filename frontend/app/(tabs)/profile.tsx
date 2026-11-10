import Ionicons from "@react-native-vector-icons/ionicons";
import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { Pressable, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { useAuth } from "@/src/auth";
import { useToast } from "@/src/components/toast";
import { Avatar, Badge, Btn, Card, Field, IconName, Rating, T, space, statusTone } from "@/src/components/ui";
import { LANGUAGES, useI18n } from "@/src/i18n";
import { usesNativeTabs } from "@/src/navigation";
import { useTheme } from "@/src/theme";

function Row({ icon, label, onPress, right, testID }: { icon: IconName; label: string; onPress: () => void; right?: React.ReactNode; testID: string }) {
  const { colors } = useTheme();
  const { rtl } = useI18n();
  return (
    <Pressable testID={testID} onPress={onPress} style={({ pressed }) => ({ flexDirection: "row", alignItems: "center", gap: space.md, minHeight: 52, opacity: pressed ? 0.6 : 1 })}>
      <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: colors.brandSoft, alignItems: "center", justifyContent: "center" }}>
        <Ionicons name={icon} size={18} color={colors.brandPrimary} />
      </View>
      <T weight="600" style={{ flex: 1 }}>{label}</T>
      {right}
      <Ionicons name={rtl ? "chevron-back" : "chevron-forward"} size={18} color={colors.muted} />
    </Pressable>
  );
}

export default function ProfileScreen() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t, lang } = useI18n();
  const { user, logout, refresh, setUser } = useAuth();
  const router = useRouter();
  const toast = useToast();
  const [edit, setEdit] = useState(false);
  const [f, setF] = useState({ name: "", phone: "", upi_id: "", bio: "" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useFocusEffect(useCallback(() => { refresh(); }, [refresh]));
  if (!user) return null;

  const save = async () => {
    setBusy(true);
    setErr("");
    try {
      setUser(await api("/me", { method: "PUT", body: f }));
      setEdit(false);
      toast(t("profile.saved"));
    } catch (e: any) {
      setErr(e.message);
    }
    setBusy(false);
  };
  const langName = LANGUAGES.find((l) => l.code === lang)?.native;

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <KeyboardAwareScrollView bottomOffset={24} contentContainerStyle={{ padding: space.lg, paddingTop: insets.top + space.lg, gap: space.lg, paddingBottom: (usesNativeTabs ? insets.bottom : 0) + space.xl }}>
        <Card style={{ backgroundColor: colors.brand, borderColor: colors.brand, gap: space.md }}>
          <View style={{ flexDirection: "row", gap: space.md, alignItems: "center" }}>
            <Avatar name={user.name} uri={user.picture} size={60} />
            <View style={{ flex: 1, gap: 2 }}>
              <T testID="profile-name" size={18} weight="800" color={colors.onBrand}>{user.name}</T>
              <T size={13} color={colors.onBrand} style={{ opacity: 0.8 }}>{user.email}</T>
              <View style={{ flexDirection: "row", gap: space.sm, marginTop: 4 }}>
                <Badge testID="profile-driver-status" icon="shield-checkmark" label={t(`verify.status.${user.driver_status}`)} tone={user.driver_status === "approved" ? "success" : statusTone(user.driver_status)} />
                {user.role === "admin" ? <Badge label="Admin" tone="accent" /> : null}
              </View>
            </View>
          </View>
          <View style={{ backgroundColor: colors.surfaceSecondary, borderRadius: 12, padding: space.sm, alignSelf: "flex-start" }}>
            <Rating value={user.rating_avg} count={user.rating_count} />
          </View>
        </Card>

        {edit ? (
          <Card style={{ gap: space.md }}>
            <Field testID="profile-name-input" label={t("auth.name")} value={f.name} onChangeText={(v) => setF({ ...f, name: v })} />
            <Field testID="profile-phone-input" label={t("auth.phone")} value={f.phone} onChangeText={(v) => setF({ ...f, phone: v })} keyboardType="phone-pad" maxLength={10} />
            <Field testID="profile-upi-input" label={t("profile.upi")} value={f.upi_id} onChangeText={(v) => setF({ ...f, upi_id: v })} autoCapitalize="none" placeholder="name@bank" />
            <Field testID="profile-bio-input" label={`${t("v2.about_me")} (${f.bio.length}/500)`} placeholder={t("v2.about_me_ph")} value={f.bio} onChangeText={(v) => setF({ ...f, bio: v })} multiline maxLength={500} />
            {err ? <T color={colors.error}>{err}</T> : null}
            <Btn testID="profile-save-button" label={t("profile.save")} onPress={save} loading={busy} />
            <Btn variant="ghost" label={t("common.cancel")} onPress={() => setEdit(false)} testID="profile-cancel-edit" />
          </Card>
        ) : (
          <Card style={{ gap: 0, paddingVertical: space.sm }}>
            <Row testID="profile-edit-row" icon="create-outline" label={t("profile.edit")} onPress={() => { setF({ name: user.name, phone: user.phone ?? "", upi_id: user.upi_id ?? "", bio: user.bio ?? "" }); setEdit(true); }} right={user.upi_id ? <T size={12} color={colors.muted}>{user.upi_id}</T> : null} />
            <Row testID="profile-language-row" icon="language-outline" label={t("profile.language")} onPress={() => router.push("/language?from=profile")} right={<T size={13} color={colors.muted}>{langName}</T>} />
            <Row testID="profile-notifications-row" icon="notifications-outline" label={t("profile.notifications")} onPress={() => router.push("/notifications")} />
            <Row testID="profile-messages-row" icon="chatbubbles-outline" label={t("v2.messages")} onPress={() => router.push("/messages")} />
            <Row testID="profile-public-row" icon="person-outline" label={t("v2.view_profile")} onPress={() => router.push(`/user/${user.user_id}`)} />
          </Card>
        )}

        <T size={13} weight="700" color={colors.muted}>{t("profile.driver").toUpperCase()}</T>
        <Card style={{ gap: 0, paddingVertical: space.sm }}>
          <Row testID="profile-verification-row" icon="shield-checkmark-outline" label={t("profile.verification")} onPress={() => router.push("/driver")} />
          <Row testID="profile-earnings-row" icon="wallet-outline" label={t("profile.earnings")} onPress={() => router.push("/earnings")} />
          <Row testID="profile-local-driver-row" icon="briefcase-outline" label={t("v2.local_register")} onPress={() => router.push("/hire/register")} />
          <Row testID="profile-hire-row" icon="key-outline" label={t("v2.hire")} onPress={() => router.push("/hire")} />
        </Card>

        <Card style={{ gap: 0, paddingVertical: space.sm }}>
          <Row testID="profile-support-row" icon="help-buoy-outline" label={t("profile.support")} onPress={() => router.push("/support")} />
          <Row testID="profile-more-row" icon="menu-outline" label={t("v2.more")} onPress={() => router.push("/more")} />
          <Row testID="profile-safety-row" icon="alert-circle-outline" label={t("profile.safety")} onPress={() => router.push("/support?tab=safety")} />
          <Row testID="profile-legal-row" icon="document-text-outline" label={t("profile.legal")} onPress={() => router.push("/legal")} />
          {user.role === "admin" ? <Row testID="profile-admin-row" icon="speedometer-outline" label={t("profile.admin")} onPress={() => router.push("/admin/login")} /> : null}
        </Card>

        <Btn testID="profile-logout-button" variant="outline" icon="log-out-outline" label={t("profile.logout")} onPress={logout} />
        <T size={11} color={colors.muted} center>TRAVOO · {t("app.tagline")}</T>
      </KeyboardAwareScrollView>
    </View>
  );
}
