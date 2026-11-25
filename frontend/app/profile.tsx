import Ionicons from "@react-native-vector-icons/ionicons";
import * as ImagePicker from "expo-image-picker";
import { manipulateAsync, SaveFormat } from "expo-image-manipulator";
import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { ActivityIndicator, Linking, Pressable, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, pictureUrl, getApiToken, API_BASE } from "@/src/api";
import { useAuth } from "@/src/auth";
import { useToast } from "@/src/components/toast";
import { Avatar, Badge, Btn, Card, Chip, Field, Header, IconName, Rating, T, radius, space, statusTone } from "@/src/components/ui";
import { PhoneOtp } from "@/src/components/PhoneOtp";
import { LANGUAGES, useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";
import { useOtpEnabled } from "@/src/useOtp";
import { useSetMode } from "@/src/useMode";
import { ModeSheet } from "@/src/components/ModeSheet";
import { uploadWithProgress } from "@/src/utils/upload";

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
  const otpOn = useOtpEnabled();
  const setMode = useSetMode();
  const [modeSheet, setModeSheet] = useState(false);
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t, lang } = useI18n();
  const { user, logout, refresh, setUser } = useAuth();
  const router = useRouter();
  const toast = useToast();
  const [edit, setEdit] = useState(false);
  const [f, setF] = useState({ name: "", dob: "", gender: "", language: "" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  const [photoProgress, setPhotoProgress] = useState(0);

  useFocusEffect(useCallback(() => { refresh(); }, [refresh]));
  if (!user) return null;

  const save = async () => {
    setBusy(true);
    setErr("");
    try {
      setUser(await api("/me", { method: "PUT", body: { name: f.name, dob: f.dob, gender: f.gender || undefined } }));
      setEdit(false);
      toast(t("profile.saved"));
    } catch (e: any) {
      setErr(e.message);
    }
    setBusy(false);
  };

  const uploadProfilePhoto = async () => {
    const perm = await ImagePicker.getMediaLibraryPermissionsAsync();
    if (!perm.granted) {
      if (!perm.canAskAgain) {
        toast("Allow photo access in Settings to choose a profile photo", "error");
        Linking.openSettings();
        return;
      }
      const req = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!req.granted) return toast("Photo access is needed to choose a profile photo", "error");
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ["images"],
      quality: 1,
      allowsEditing: true,
      aspect: [1, 1],
    });
    if (result.canceled || !result.assets?.[0]) return;

    setUploadingPhoto(true);
    setPhotoProgress(0);
    try {
      const actions = result.assets[0].width && result.assets[0].width > 800 ? [{ resize: { width: 800 } }] : [];
      const compressed = await manipulateAsync(result.assets[0].uri, actions, { compress: 0.8, format: SaveFormat.JPEG });
      const picked = { uri: compressed.uri, name: `profile_${Date.now()}.jpg`, mimeType: "image/jpeg", isPdf: false };

      // Upload to the new user profile photo endpoint
      const r = await uploadWithProgress(`${API_BASE}/me/photo`, picked, {
        headers: { Authorization: `Bearer ${getApiToken()}` },
        onProgress: (p) => setPhotoProgress(p),
      });
      let body: any = {};
      try { body = JSON.parse(r.body || "{}"); } catch { body = {}; }
      
      if (r.status >= 200 && r.status < 300) {
        toast("Profile photo updated successfully");
        await refresh();
      } else {
        toast(body.detail || "Failed to upload photo", "error");
      }
    } catch (e: any) {
      toast(e.message || "Failed to upload photo", "error");
    }
    setUploadingPhoto(false);
    setPhotoProgress(0);
  };
  const langName = LANGUAGES.find((l) => l.code === lang)?.native;

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <Header title={t("tab.profile")} />
      <KeyboardAwareScrollView bottomOffset={24} contentContainerStyle={{ padding: space.lg, gap: space.lg, paddingBottom: insets.bottom + space.xl }}>
        <View testID="profile-header" style={{ alignItems: "center", gap: 6 }}>
          <Pressable testID="profile-photo-button" accessibilityLabel="Change profile photo" onPress={uploadProfilePhoto} disabled={uploadingPhoto} hitSlop={20}>
            <Avatar name={user.name} uri={pictureUrl(user.picture)} size={96} />
            <View style={{ position: "absolute", bottom: 0, right: 0, backgroundColor: colors.onSurface, borderRadius: 16, width: 32, height: 32, alignItems: "center", justifyContent: "center", borderWidth: 3, borderColor: colors.surface }}>
              {uploadingPhoto ? <ActivityIndicator size="small" color="white" /> : <Ionicons name="camera" size={15} color="#fff" />}
            </View>
          </Pressable>
          <T testID="profile-name" size={22} weight="800">{user.name}</T>
          <T size={13} color={colors.muted}>{user.phone ? `+91 ${user.phone}` : user.email ?? (user.phone_e164 ? `+${user.phone_e164}` : "")}</T>
          <View style={{ flexDirection: "row", gap: space.sm }}>
            {user.driver_status === "approved" ? <Badge testID="profile-driver-status" icon="shield-checkmark" label="Verified Driver" tone="warning" />
              : user.driver_status && user.driver_status !== "not_submitted" ? <Badge testID="profile-driver-status" label={t(`verify.status.${user.driver_status}`)} tone={statusTone(user.driver_status)} /> : null}
            {user.role === "admin" ? <Badge label="Admin" tone="accent" /> : null}
          </View>
          {user.account_type === "driver" || user.rating_count ? <Rating value={user.rating_avg} count={user.rating_count} /> : null}
        </View>

        {otpOn && !user.phone_verified ? (
          <Card testID="profile-verify-phone-card" style={{ gap: space.md }}>
            <T weight="800">Verify your mobile number</T>
            <T size={12} color={colors.muted}>Sign in with OTP next time and use it for driver verification. Your email login keeps working.</T>
            <PhoneOtp testPrefix="link" sendPath="/me/phone/send" verifyPath="/me/phone/verify" submitLabel="Verify number" onVerified={async () => { await refresh(); toast("Mobile number verified"); }} />
          </Card>
        ) : null}

        <Pressable testID="profile-switch-mode-row" onPress={() => setModeSheet(true)} style={{ flexDirection: "row", alignItems: "center", gap: space.md, padding: space.md, borderRadius: radius.lg, backgroundColor: colors.brandSoft }}>
          <Ionicons name="swap-horizontal" size={26} color={colors.brandPrimary} />
          <View style={{ flex: 1 }}>
            <T weight="800">Change Role</T>
            <T size={12} color={colors.muted}>Now: {(user.account_type ?? "passenger") === "driver" ? "Driver" : "Passenger"} · change to {(user.account_type ?? "passenger") === "driver" ? "Passenger" : "Driver"}</T>
          </View>
          <Ionicons name="chevron-forward" size={20} color={colors.muted} />
        </Pressable>
        <ModeSheet open={modeSheet} current={user.account_type ?? "passenger"} onClose={() => setModeSheet(false)}
          onSwitch={async (m) => { try { await setMode(m); setModeSheet(false); toast(m === "driver" ? "You're now a Driver" : "You're now a Passenger"); router.replace("/"); } catch (e: any) { toast(e.message, "error"); } }} />

        <Card testID="personal-profile-card" style={{ gap: space.sm, padding: space.md, backgroundColor: colors.surfaceSecondary, borderRadius: radius.lg, shadowColor: "#000", shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.1, shadowRadius: 4, elevation: 3 }}>
          <View style={{ flexDirection: "row", alignItems: "center", gap: space.sm }}>
            <Ionicons name="person-circle" size={24} color={colors.brandPrimary} />
            <T weight="800" size={16}>Personal</T>
          </View>
          {edit ? (
            <View style={{ gap: space.md }}>
              <Field testID="profile-name-input" label="Full Name" value={f.name} onChangeText={(v) => setF({ ...f, name: v })} />
              <Field testID="profile-dob-input" label="Date of Birth" value={f.dob} onChangeText={(v) => setF({ ...f, dob: v })} placeholder="DD-MM-YYYY" maxLength={10} />
              <T size={13} weight="600" color={colors.muted}>Gender</T>
              <View style={{ flexDirection: "row", gap: space.sm }}>
                {["male", "female", "other"].map((g) => <Chip key={g} testID={`profile-gender-${g}`} label={g[0].toUpperCase() + g.slice(1)} active={f.gender === g} onPress={() => setF({ ...f, gender: g })} />)}
              </View>
              {err ? <T color={colors.error}>{err}</T> : null}
              <Btn testID="profile-save-button" label={t("profile.save")} onPress={save} loading={busy} />
              <Btn variant="ghost" label={t("common.cancel")} onPress={() => setEdit(false)} testID="profile-cancel-edit" />
            </View>
          ) : (
            <View style={{ gap: 0 }}>
              <Row testID="profile-name-row" icon="person-outline" label="Full Name" onPress={() => { setF({ name: user.name, dob: user.dob ?? "", gender: user.gender ?? "", language: lang }); setEdit(true); }} right={<T size={13} color={colors.muted}>{user.name}</T>} />
              <Row testID="profile-dob-row" icon="calendar-outline" label="Date of Birth" onPress={() => { setF({ name: user.name, dob: user.dob ?? "", gender: user.gender ?? "", language: lang }); setEdit(true); }} right={<T size={13} color={colors.muted}>{user.dob || "Not set"}</T>} />
              <Row testID="profile-gender-row" icon="person-outline" label="Gender" onPress={() => { setF({ name: user.name, dob: user.dob ?? "", gender: user.gender ?? "", language: lang }); setEdit(true); }} right={<T size={13} color={colors.muted}>{user.gender ? user.gender[0].toUpperCase() + user.gender.slice(1) : "Not set"}</T>} />
              <Row testID="profile-language-row" icon="language-outline" label={t("profile.language")} onPress={() => router.push("/language")} right={<T size={13} color={colors.muted}>{langName}</T>} />
            </View>
          )}
        </Card>

        <Card testID="driver-section-card" style={{ gap: space.sm, padding: space.md, backgroundColor: colors.surfaceSecondary, borderRadius: radius.lg, shadowColor: "#000", shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.1, shadowRadius: 4, elevation: 3 }}>
          <View style={{ flexDirection: "row", alignItems: "center", gap: space.sm }}>
            <Ionicons name="car-sport" size={24} color={colors.brandPrimary} />
            <T weight="800" size={16}>Driver</T>
          </View>
          <View style={{ gap: 0 }}>
            <Row testID="profile-local-driver-row" icon="briefcase-outline" label="Local Driver" onPress={() => router.push("/hire/register")} />
            <Row testID="profile-verification-row" icon="shield-checkmark-outline" label="Carpool Driver Verification" onPress={() => router.push("/driver")} />
            <Row testID="profile-documents-row" icon="document-text-outline" label="My Documents" onPress={() => router.push("/hire/register?view=details")} />
            <Row testID="profile-vehicles-row" icon="car-outline" label="My Vehicles" onPress={() => router.push("/hire/vehicles")} />
            <Row testID="profile-earnings-row" icon="wallet-outline" label={t("profile.earnings")} onPress={() => router.push("/earnings")} />
          </View>
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
