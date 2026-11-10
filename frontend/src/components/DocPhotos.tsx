import Ionicons from "@react-native-vector-icons/ionicons";
import * as DocumentPicker from "expo-document-picker";
import { Image } from "expo-image";
import { manipulateAsync, SaveFormat } from "expo-image-manipulator";
import * as ImagePicker from "expo-image-picker";
import * as WebBrowser from "expo-web-browser";
import React, { useState } from "react";
import { ActivityIndicator, Linking, Modal, Pressable, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { API_BASE, api, fileUrl, getApiToken } from "@/src/api";
import { useToast } from "@/src/components/toast";
import { Btn, T, radius, space } from "@/src/components/ui";
import { useTheme } from "@/src/theme";
import { uploadWithProgress } from "@/src/utils/upload";

export type DocFile = { file_id: string; kind: string; content_type: string; size: number; original_name?: string };
export type DocKind = { kind: string; label: string; required: boolean; max: number; pdf: boolean };
type Picked = { uri: string; name: string; mimeType: string; isPdf: boolean; size?: number };
type Sheet = { kind: DocKind; mode: "pick" | "preview" | "manage"; file?: DocFile } | null;
type Source = "camera" | "gallery";

const ICONS: Record<string, any> = { profile: "person-circle-outline", licence_front: "card-outline", licence_back: "card-outline", licence: "card-outline",
  id_proof: "finger-print-outline", rc: "document-text-outline", insurance: "shield-checkmark-outline", vehicle: "car-sport-outline", other: "folder-open-outline" };
const MAX_BYTES = 10 * 1024 * 1024;

/** Compress camera/gallery photos to JPEG (max 1600px wide) so uploads stay small and HEIC never reaches the server. */
async function compress(asset: ImagePicker.ImagePickerAsset): Promise<Picked> {
  const actions = asset.width && asset.width > 1600 ? [{ resize: { width: 1600 } }] : [];
  const out = await manipulateAsync(asset.uri, actions, { compress: 0.72, format: SaveFormat.JPEG });
  return { uri: out.uri, name: `photo_${Date.now()}.jpg`, mimeType: "image/jpeg", isPdf: false };
}

const isNetworkError = (e: any) => /network|timed out|connection|failed to fetch/i.test(String(e?.message ?? e));

/** Driver verification uploader: camera, gallery or PDF, preview before upload, progress, retry, replace and delete. */
export function DocPhotos({ files, kinds, editable, onChanged }: { files: DocFile[]; kinds: DocKind[]; editable: boolean; onChanged: () => void }) {
  const { colors } = useTheme();
  const toast = useToast();
  const insets = useSafeAreaInsets();
  const [sheet, setSheet] = useState<Sheet>(null);
  const [picked, setPicked] = useState<Picked | null>(null);
  const [perm, setPerm] = useState<{ source: Source; blocked: boolean } | null>(null);
  const [progress, setProgress] = useState<Record<string, number>>({});
  const [failed, setFailed] = useState<Record<string, { msg: string; file: Picked }>>({});

  const close = () => { setSheet(null); setPerm(null); setPicked(null); };

  const doUpload = async (kind: string, f: Picked) => {
    setFailed((x) => { const n = { ...x }; delete n[kind]; return n; });
    setProgress((x) => ({ ...x, [kind]: 0 }));
    let lastErr: any;
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        const r = await uploadWithProgress(`${API_BASE}/driver/documents/${kind}`, f, {
          headers: { Authorization: `Bearer ${getApiToken()}` },
          onProgress: (p) => setProgress((x) => ({ ...x, [kind]: p })),
        });
        let body: any = {};
        try { body = JSON.parse(r.body || "{}"); } catch { body = {}; }
        if (r.status >= 200 && r.status < 300) {
          setProgress((x) => { const n = { ...x }; delete n[kind]; return n; });
          toast(body.duplicate ? "This file was already uploaded" : "Uploaded");
          onChanged();
          return;
        }
        lastErr = new Error(body.detail || `Upload failed (error ${r.status})`);
        if (r.status < 500) break; // validation errors will not fix themselves
      } catch (e: any) {
        lastErr = e;
        if (!isNetworkError(e)) break;
      }
      await new Promise((res) => setTimeout(res, 1500 * (attempt + 1)));
    }
    setProgress((x) => { const n = { ...x }; delete n[kind]; return n; });
    setFailed((x) => ({ ...x, [kind]: { msg: lastErr?.message || "Upload failed", file: f } }));
  };

  const launch = async (s: Source) => {
    const opts: ImagePicker.ImagePickerOptions = { mediaTypes: ["images"], quality: 1, allowsEditing: false };
    try {
      const r = s === "camera" ? await ImagePicker.launchCameraAsync(opts) : await ImagePicker.launchImageLibraryAsync(opts);
      setPerm(null);
      if (r.canceled || !r.assets?.[0]) return;
      const p = await compress(r.assets[0]);
      setPicked(p);
      setSheet((x) => (x ? { ...x, mode: "preview" } : x));
    } catch (e: any) {
      toast(e.message || "Could not open the camera or gallery", "error");
    }
  };

  const choose = async (s: Source) => {
    const p = s === "camera" ? await ImagePicker.getCameraPermissionsAsync() : await ImagePicker.getMediaLibraryPermissionsAsync();
    if (p.granted) return launch(s);
    setPerm({ source: s, blocked: !p.canAskAgain });
  };

  const allow = async () => {
    if (!perm) return;
    const p = perm.source === "camera" ? await ImagePicker.requestCameraPermissionsAsync() : await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (p.granted) return launch(perm.source);
    setPerm({ source: perm.source, blocked: !p.canAskAgain });
  };

  const pickFile = async () => {
    const r = await DocumentPicker.getDocumentAsync({ type: ["application/pdf", "image/jpeg", "image/png"], copyToCacheDirectory: true, multiple: false });
    if (r.canceled || !r.assets?.[0]) return;
    const a = r.assets[0];
    if (a.size && a.size > MAX_BYTES) return toast("File is larger than 10 MB. Please choose a smaller file.", "error");
    const isPdf = (a.mimeType ?? "").includes("pdf") || a.name.toLowerCase().endsWith(".pdf");
    setPicked({ uri: a.uri, name: a.name, mimeType: isPdf ? "application/pdf" : a.mimeType || "image/jpeg", isPdf, size: a.size });
    setSheet((x) => (x ? { ...x, mode: "preview" } : x));
  };

  const remove = async (f: DocFile) => {
    try {
      await api(`/driver/documents/file/${f.file_id}`, { method: "DELETE" });
      toast("Removed");
      close();
      onChanged();
    } catch (e: any) {
      toast(e.message, "error");
    }
  };

  const tile = (k: DocKind, f?: DocFile, idx = 0) => {
    const busy = progress[k.kind] !== undefined && !f;
    const fail = !f ? failed[k.kind] : undefined;
    const id = f ? `doc-file-${k.kind}-${idx}` : `doc-photo-${k.kind}`;
    return (
      <Pressable key={f?.file_id ?? `${k.kind}-add`} testID={id} disabled={busy || (!editable && !f)}
        onPress={() => setSheet({ kind: k, mode: f ? "manage" : "pick", file: f })}
        style={{ width: "47%", flexGrow: 1, aspectRatio: 1.25, borderRadius: radius.md, borderWidth: 1, borderStyle: f ? "solid" : "dashed",
          borderColor: fail ? colors.error : f ? colors.success : colors.borderStrong, backgroundColor: colors.surfaceTertiary, overflow: "hidden", alignItems: "center", justifyContent: "center" }}>
        {f && f.content_type !== "application/pdf" ? <Image source={{ uri: fileUrl(f.file_id) }} style={{ position: "absolute", width: "100%", height: "100%" }} contentFit="cover" />
          : <Ionicons name={f ? "document-attach-outline" : ICONS[k.kind] ?? "document-outline"} size={30} color={fail ? colors.error : colors.brandPrimary} />}
        {f?.content_type === "application/pdf" ? <T size={11} weight="700" color={colors.muted}>PDF</T> : null}
        <View style={{ position: "absolute", left: 0, right: 0, bottom: 0, paddingVertical: space.xs, paddingHorizontal: space.xs, backgroundColor: f ? colors.brand : "transparent", alignItems: "center", gap: 2 }}>
          {busy ? (
            <View testID={`doc-progress-${k.kind}`} style={{ width: "86%", height: 6, borderRadius: 3, backgroundColor: colors.border, overflow: "hidden" }}>
              <View style={{ width: `${Math.round((progress[k.kind] ?? 0) * 100)}%`, height: "100%", backgroundColor: colors.brandPrimary }} />
            </View>
          ) : null}
          <T size={10} weight="700" color={f ? colors.onBrand : fail ? colors.error : colors.onSurface} numberOfLines={2} center>
            {busy ? `Uploading ${Math.round((progress[k.kind] ?? 0) * 100)}%` : fail ? "Upload failed · tap to retry" : `${k.label}${k.required && !f ? " *" : ""}`}
          </T>
        </View>
      </Pressable>
    );
  };

  const sk = sheet?.kind;
  return (
    <View style={{ gap: space.md }}>
      {kinds.map((k) => {
        const mine = files.filter((f) => f.kind === k.kind || (k.kind === "licence_front" && f.kind === "licence"));
        const canAdd = editable && mine.length < k.max;
        if (k.max === 1) return <View key={k.kind} style={{ flexDirection: "row" }}>{mine[0] ? tile(k, mine[0]) : editable ? tile(k) : tile(k)}</View>;
        return (
          <View key={k.kind} style={{ gap: space.xs }}>
            <T size={12} weight="700" color={colors.muted}>{k.label} ({mine.length}/{k.max}){k.required ? " *" : ""}</T>
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.sm }}>
              {mine.map((f, i) => tile(k, f, i))}
              {canAdd ? tile(k) : null}
            </View>
          </View>
        );
      })}
      {Object.entries(failed).map(([kind, f]) => (
        <View key={kind} testID={`doc-error-${kind}`} style={{ flexDirection: "row", alignItems: "center", gap: space.sm, backgroundColor: colors.surfaceTertiary, padding: space.sm, borderRadius: radius.md }}>
          <Ionicons name="alert-circle" size={18} color={colors.error} />
          <T size={12} color={colors.error} style={{ flex: 1 }}>{kinds.find((k) => k.kind === kind)?.label}: {f.msg}</T>
          <Btn small testID={`doc-retry-${kind}`} label="Retry" onPress={() => doUpload(kind, f.file)} />
        </View>
      ))}
      <Modal visible={!!sheet} transparent animationType="slide" onRequestClose={close}>
        <Pressable style={{ flex: 1, backgroundColor: colors.scrim }} onPress={close} />
        <View testID="doc-photo-sheet" style={{ backgroundColor: colors.surfaceSecondary, borderTopLeftRadius: radius.lg, borderTopRightRadius: radius.lg, padding: space.lg, paddingBottom: insets.bottom + space.lg, gap: space.md }}>
          <T size={18} weight="800" center>{sk?.label}</T>
          {sheet?.mode === "manage" && sheet.file ? (
            <>
              {sheet.file.content_type === "application/pdf" ? (
                <Btn testID="doc-open-pdf-button" variant="outline" icon="open-outline" label="Open PDF" onPress={() => WebBrowser.openBrowserAsync(fileUrl(sheet.file!.file_id))} />
              ) : (
                <Image testID="doc-manage-preview" source={{ uri: fileUrl(sheet.file.file_id) }} style={{ width: "100%", height: 240, borderRadius: radius.md }} contentFit="contain" />
              )}
              {editable ? (
                <View style={{ flexDirection: "row", gap: space.sm }}>
                  {sk && sk.max === 1 ? <Btn testID="doc-replace-button" style={{ flex: 1 }} icon="swap-horizontal" label="Replace" onPress={() => setSheet({ kind: sk, mode: "pick" })} /> : null}
                  <Btn testID="doc-delete-button" style={{ flex: 1 }} variant="danger" icon="trash-outline" label="Delete" onPress={() => remove(sheet.file!)} />
                </View>
              ) : null}
            </>
          ) : sheet?.mode === "preview" && picked ? (
            <>
              {picked.isPdf ? (
                <View style={{ alignItems: "center", gap: space.sm, padding: space.lg }}>
                  <Ionicons name="document-text" size={56} color={colors.brandPrimary} />
                  <T testID="doc-preview-name" weight="700" center>{picked.name}</T>
                </View>
              ) : (
                <Image testID="doc-preview-image" source={{ uri: picked.uri }} style={{ width: "100%", height: 260, borderRadius: radius.md }} contentFit="contain" />
              )}
              <T size={12} color={colors.muted} center>Make sure all text is sharp and readable before uploading.</T>
              <View style={{ flexDirection: "row", gap: space.sm }}>
                <Btn testID="doc-preview-retake" style={{ flex: 1 }} variant="outline" label="Choose another" onPress={() => { setPicked(null); setSheet({ kind: sk!, mode: "pick" }); }} />
                <Btn testID="doc-preview-upload" style={{ flex: 1 }} icon="cloud-upload-outline" label="Upload" onPress={() => { const k = sk!.kind, f = picked; close(); doUpload(k, f); }} />
              </View>
            </>
          ) : perm ? (
            <>
              <T color={colors.muted} center>{perm.source === "camera" ? "Allow camera access to photograph your documents" : "Allow photo access to choose document pictures"}</T>
              {perm.blocked ? <Btn testID="doc-open-settings-button" icon="settings-outline" label="Open Settings" onPress={() => Linking.openSettings()} />
                : <Btn testID="doc-allow-permission-button" label="Allow access" onPress={allow} />}
            </>
          ) : (
            <>
              {sk && failed[sk.kind] ? <Btn testID="doc-sheet-retry" label="Retry last upload" icon="refresh" onPress={() => { const k = sk.kind, f = failed[k].file; close(); doUpload(k, f); }} /> : null}
              <View style={{ flexDirection: "row", gap: space.sm }}>
                <Btn testID="doc-camera-button" style={{ flex: 1 }} icon="camera-outline" label="Camera" onPress={() => choose("camera")} />
                <Btn testID="doc-gallery-button" style={{ flex: 1 }} variant="outline" icon="images-outline" label="Gallery" onPress={() => choose("gallery")} />
              </View>
              {sk?.pdf ? <Btn testID="doc-file-button" variant="outline" icon="document-attach-outline" label="Choose PDF or file" onPress={pickFile} /> : null}
              <T size={11} color={colors.muted} center>JPG or PNG{sk?.pdf ? " or PDF" : ""} · max 10 MB</T>
            </>
          )}
          <Btn testID="doc-sheet-cancel" variant="ghost" label="Cancel" onPress={close} />
        </View>
      </Modal>
      {Object.keys(progress).length ? <ActivityIndicator testID="doc-uploading-indicator" color={colors.brandPrimary} /> : null}
    </View>
  );
}
