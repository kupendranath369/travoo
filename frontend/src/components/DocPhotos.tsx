import Ionicons from "@react-native-vector-icons/ionicons";
import { Image } from "expo-image";
import * as ImagePicker from "expo-image-picker";
import React, { useState } from "react";
import { ActivityIndicator, Linking, Modal, Platform, Pressable, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { API_BASE, fileUrl, getApiToken } from "@/src/api";
import { useToast } from "@/src/components/toast";
import { Btn, T, radius, space } from "@/src/components/ui";
import { useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";
import { uploadForm } from "@/src/utils/upload";

export const DOC_KINDS = ["profile", "licence", "rc", "vehicle"] as const;
const ICONS: Record<string, any> = { profile: "person-circle-outline", licence: "card-outline", rc: "document-text-outline", vehicle: "car-sport-outline" };

type Source = "camera" | "gallery";
type PermState = { source: Source; blocked: boolean } | null;

/** Grid of the 4 verification photos. Uploads go to private object storage via the backend. */
export function DocPhotos({ photos, editable, onUploaded }: { photos: Record<string, string>; editable: boolean; onUploaded: () => void }) {
  const { colors } = useTheme();
  const { t } = useI18n();
  const toast = useToast();
  const insets = useSafeAreaInsets();
  const [kind, setKind] = useState<string | null>(null);
  const [perm, setPerm] = useState<PermState>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const getPerm = (s: Source) => (s === "camera" ? ImagePicker.getCameraPermissionsAsync() : ImagePicker.getMediaLibraryPermissionsAsync());
  const askPerm = (s: Source) => (s === "camera" ? ImagePicker.requestCameraPermissionsAsync() : ImagePicker.requestMediaLibraryPermissionsAsync());

  const upload = async (k: string, asset: ImagePicker.ImagePickerAsset) => {
    setBusy(k);
    try {
      console.log(`Uploading ${k}:`, { uri: asset.uri, fileName: asset.fileName, mimeType: asset.mimeType, fileSize: asset.fileSize });
      
      // Handle mobile file URI - ensure we have a valid URI
      const fileUri = asset.uri;
      if (!fileUri) {
        throw new Error("No file URI provided");
      }
      
      // Generate a proper filename
      const fileName = asset.fileName || `${k}_${Date.now()}.jpg`;
      const mimeType = asset.mimeType || "image/jpeg";
      
      console.log(`Starting upload to ${API_BASE}/driver/documents/${k}`);
      
      const res = await uploadForm(`${API_BASE}/driver/documents/${k}`, {
        headers: { Authorization: `Bearer ${getApiToken()}` },
        files: { file: { uri: fileUri, name: fileName, mimeType } },
      });
      
      console.log(`Upload response for ${k}:`, res.status, res.statusText);
      
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        console.error(`Upload failed for ${k}:`, d);
        throw new Error((d as any).detail || `Upload failed with status ${res.status}`);
      }
      
      const result = await res.json();
      console.log(`Upload success for ${k}:`, result);
      
      toast(`${t(`verify.photo.${k}`)} · ${t("verify.uploaded")}`);
      onUploaded();
    } catch (e: any) {
      console.error(`Upload error for ${k}:`, e);
      toast(e.message || "Upload failed. Please try again.", "error");
    }
    setBusy(null);
  };

  const launch = async (s: Source) => {
    const k = kind!;
    const opts: ImagePicker.ImagePickerOptions = { 
      mediaTypes: ["images"], 
      quality: 0.8, 
      allowsEditing: false, // Disable editing completely to avoid issues
    };
    try {
      console.log(`Launching ${s} for ${k}`);
      const r = s === "camera" ? await ImagePicker.launchCameraAsync(opts) : await ImagePicker.launchImageLibraryAsync(opts);
      setKind(null);
      setPerm(null);
      
      if (!r.canceled && r.assets && r.assets[0]) {
        console.log(`Selected ${k} from ${s}:`, r.assets[0]);
        upload(k, r.assets[0]);
      } else {
        console.log(`User canceled ${s} for ${k}`);
      }
    } catch (e: any) {
      console.error(`Error launching ${s} for ${k}:`, e);
      toast(e.message || "Failed to open camera/gallery", "error");
      setKind(null);
      setPerm(null);
    }
  };

  const choose = async (s: Source) => {
    try {
      const p = await getPerm(s);
      if (p.granted) return launch(s);
      setPerm({ source: s, blocked: !p.canAskAgain }); // show why we need it before the system prompt
    } catch (e: any) {
      console.error(`Permission check error for ${s}:`, e);
      toast("Failed to check permissions", "error");
    }
  };

  const allow = async () => {
    if (!perm) return;
    const p = await askPerm(perm.source);
    if (p.granted) return launch(perm.source);
    setPerm({ source: perm.source, blocked: !p.canAskAgain });
  };

  return (
    <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.md }}>
      {DOC_KINDS.map((k) => {
        const fid = photos?.[k];
        return (
          <Pressable key={k} testID={`doc-photo-${k}`} disabled={!editable || busy === k} onPress={() => setKind(k)} style={{ width: Platform.OS === "web" ? "47%" : "48%", flexGrow: 1, aspectRatio: 1.2, borderRadius: radius.md, borderWidth: 1, borderStyle: fid ? "solid" : "dashed", borderColor: fid ? colors.success : colors.borderStrong, backgroundColor: colors.surfaceTertiary, overflow: "hidden", alignItems: "center", justifyContent: "center" }}>
            {fid ? <Image source={{ uri: fileUrl(fid) }} style={{ position: "absolute", width: "100%", height: "100%" }} contentFit="cover" /> : <Ionicons name={ICONS[k]} size={30} color={colors.brandPrimary} />}
            <View style={{ position: "absolute", left: 0, right: 0, bottom: 0, padding: space.xs, backgroundColor: fid ? colors.brand : "transparent", flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 4, paddingHorizontal: space.sm }}>
              {busy === k ? <ActivityIndicator size="small" color={fid ? colors.onBrand : colors.brandPrimary} /> : fid ? <Ionicons name="checkmark-circle" size={14} color={colors.onBrand} /> : null}
              <T size={11} weight="700" color={fid ? colors.onBrand : colors.onSurface} numberOfLines={2} center style={{ flex: 1 }}>{t(`verify.photo.${k}`)}</T>
            </View>
          </Pressable>
        );
      })}
      <Modal visible={!!kind} transparent animationType="slide" onRequestClose={() => { setKind(null); setPerm(null); }}>
        <Pressable style={{ flex: 1, backgroundColor: colors.scrim }} onPress={() => { setKind(null); setPerm(null); }} />
        <View testID="doc-photo-sheet" style={{ backgroundColor: colors.surfaceSecondary, borderTopLeftRadius: radius.lg, borderTopRightRadius: radius.lg, padding: space.lg, paddingBottom: insets.bottom + space.lg, gap: space.md }}>
          <T size={18} weight="800" center>{kind ? t(`verify.photo.${kind}`) : ""}</T>
          {perm ? (
            <>
              <T color={colors.muted} center>{t(perm.source === "camera" ? "verify.perm_camera" : "verify.perm_gallery")}</T>
              {perm.blocked ? (
                <Btn testID="doc-open-settings-button" icon="settings-outline" label={t("loc.settings")} onPress={() => Linking.openSettings()} />
              ) : (
                <Btn testID="doc-allow-permission-button" label={t("verify.allow")} onPress={allow} />
              )}
            </>
          ) : (
            <View style={{ flexDirection: "row", gap: space.sm }}>
              <Btn testID="doc-camera-button" style={{ flex: 1 }} icon="camera-outline" label={t("verify.camera")} onPress={() => choose("camera")} />
              <Btn testID="doc-gallery-button" style={{ flex: 1 }} variant="outline" icon="images-outline" label={t("verify.gallery")} onPress={() => choose("gallery")} />
            </View>
          )}
          <Btn testID="doc-sheet-cancel" variant="ghost" label={t("common.cancel")} onPress={() => { setKind(null); setPerm(null); }} />
        </View>
      </Modal>
    </View>
  );
}
