import Ionicons from "@react-native-vector-icons/ionicons";
import React, { useState } from "react";
import { Pressable, ScrollView, View, ViewStyle } from "react-native";

import { IconName, T, radius, space } from "@/src/components/ui";
import { useTheme } from "@/src/theme";

export const float: ViewStyle = { shadowColor: "#0B2447", shadowOpacity: 0.08, shadowRadius: 14, shadowOffset: { width: 0, height: 6 }, elevation: 3 };

export const LANG_OPTIONS = ["Kannada", "Hindi", "English", "Tamil", "Telugu", "Malayalam", "Marathi", "Gujarati", "Bengali", "Punjabi", "Odia", "Urdu",
  "Assamese", "Konkani", "Tulu", "Bhojpuri", "Rajasthani", "Kashmiri", "Maithili", "Nepali", "Sindhi", "Manipuri"];

export const PRO_STATUS: Record<string, { label: string; tone: "info" | "success" | "warning" | "error" | "muted"; icon: IconName; text: string }> = {
  none: { label: "Not registered", tone: "muted", icon: "person-add-outline", text: "Register once to offer Rent a Driver and Book a Driver." },
  under_review: { label: "Verification pending", tone: "warning", icon: "time-outline", text: "Travoo is checking your documents. We will notify you after the review." },
  approved: { label: "Approved", tone: "success", icon: "shield-checkmark", text: "You are a verified Travoo local driver." },
  rejected: { label: "Rejected", tone: "error", icon: "close-circle-outline", text: "Your registration was not approved. Fix the items below and submit again." },
  resubmit: { label: "Resubmission required", tone: "warning", icon: "refresh-circle-outline", text: "Please correct the items below and submit again." },
};

export const ITEM_LABEL: Record<string, string> = { home: "Home location", languages: "Languages", licence_no: "Licence number", licence_expiry: "Licence expiry",
  licence_front: "Licence front photo", licence_back: "Licence back photo", id_proof: "Aadhaar front photo", vehicles: "Vehicle details" };

export const COMMERCIAL: Record<string, { label: string; tone: "info" | "success" | "warning" | "error" | "muted" }> = {
  approved: { label: "Approved for Book a Driver", tone: "success" }, pending: { label: "Approval pending", tone: "warning" },
  rejected: { label: "Not approved", tone: "error" }, none: { label: "Carpool only", tone: "muted" },
};

export function Progress({ step, labels }: { step: number; total?: number; labels: string[] }) {
  const { colors } = useTheme();
  return (
    <View testID="pro-progress" style={{ flexDirection: "row", alignItems: "flex-start" }}>
      {labels.map((l, i) => (
        <React.Fragment key={l}>
          <View style={{ alignItems: "center", gap: 4, width: 92 }}>
            <View testID={`pro-progress-step-${i + 1}`} style={{ width: 38, height: 38, borderRadius: 19, alignItems: "center", justifyContent: "center",
              backgroundColor: i <= step ? colors.brandSecondary : colors.surfaceSecondary, borderWidth: 2, borderColor: i <= step ? colors.brandSecondary : colors.border }}>
              {i < step ? <Ionicons name="checkmark" size={18} color="#fff" /> : <T weight="800" color={i <= step ? "#fff" : colors.muted}>{i + 1}</T>}
            </View>
            <T testID={i === step ? "pro-progress-label" : undefined} size={11} weight={i === step ? "800" : "500"} center color={i === step ? colors.onSurface : colors.muted}>{l}</T>
          </View>
          {i < labels.length - 1 ? <View style={{ flex: 1, height: 2, marginTop: 18, backgroundColor: i < step ? colors.brandSecondary : colors.border }} /> : null}
        </React.Fragment>
      ))}
    </View>
  );
}

export function ServiceCard({ title, desc, icon, active, onPress, testID, note, disabled }: { title: string; desc: string; icon: IconName; active: boolean; onPress: () => void; testID: string; note?: string; disabled?: boolean }) {
  const { colors } = useTheme();
  return (
    <Pressable testID={testID} onPress={onPress} disabled={disabled} accessibilityRole="checkbox" accessibilityState={{ checked: active, disabled }}
      style={({ pressed }) => [float, { flex: 1, minHeight: 148, padding: space.md, gap: space.sm, borderRadius: radius.lg, backgroundColor: active ? colors.accentSoft : colors.surfaceSecondary,
        borderWidth: 2, borderColor: active ? colors.brandTertiary : "transparent", opacity: disabled ? 0.8 : 1, transform: [{ scale: pressed ? 0.98 : 1 }] }]}>
      <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
        <View style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: active ? colors.brandTertiary : colors.surfaceTertiary, alignItems: "center", justifyContent: "center" }}>
          <Ionicons name={icon} size={22} color={active ? "#fff" : colors.onSurface} />
        </View>
        <Ionicons name={active ? "checkmark-circle" : "ellipse-outline"} size={24} color={active ? colors.brandTertiary : colors.borderStrong} />
      </View>
      <T weight="800" size={15}>{title}</T>
      <T size={12} color={colors.muted}>{desc}</T>
      {note ? <T size={11} weight="700" color={colors.brandTertiary}>{note}</T> : null}
    </Pressable>
  );
}

export function Tile({ icon, label, onPress, testID, badge }: { icon: IconName; label: string; onPress: () => void; testID: string; badge?: number }) {
  const { colors } = useTheme();
  return (
    <Pressable testID={testID} onPress={onPress} style={({ pressed }) => [float, { width: "48%", padding: space.md, gap: space.sm, borderRadius: radius.lg,
      backgroundColor: colors.surfaceSecondary, transform: [{ scale: pressed ? 0.97 : 1 }] }]}>
      <View style={{ width: 40, height: 40, borderRadius: 12, backgroundColor: colors.accentSoft, alignItems: "center", justifyContent: "center" }}>
        <Ionicons name={icon} size={20} color={colors.brandTertiary} />
      </View>
      <T weight="700" size={14}>{label}</T>
      {badge ? <View testID={`${testID}-badge`} style={{ position: "absolute", top: space.sm, right: space.sm, minWidth: 22, height: 22, borderRadius: 11, paddingHorizontal: 6, backgroundColor: colors.error, alignItems: "center", justifyContent: "center" }}>
        <T size={11} weight="800" color="#fff">{badge}</T>
      </View> : null}
    </Pressable>
  );
}

export function ChipSelect({ options, value, onChange, testPrefix }: { options: string[]; value: string[]; onChange: (v: string[]) => void; testPrefix: string }) {
  const { colors } = useTheme();
  return (
    <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.sm }}>
      {options.map((o) => {
        const on = value.includes(o);
        return (
          <Pressable key={o} testID={`${testPrefix}-${o.toLowerCase()}`} onPress={() => onChange(on ? value.filter((x) => x !== o) : [...value, o])}
            style={[on ? float : null, { flexDirection: "row", alignItems: "center", gap: 4, minHeight: 40, paddingHorizontal: space.md, borderRadius: radius.pill,
              backgroundColor: on ? colors.brandTertiary : colors.surfaceSecondary, borderWidth: 1, borderColor: on ? colors.brandTertiary : colors.border }]}>
            {on ? <Ionicons name="checkmark" size={14} color="#fff" /> : null}
            <T size={13} weight="700" color={on ? "#fff" : colors.onSurface}>{o}</T>
          </Pressable>
        );
      })}
    </View>
  );
}

/** Pick languages one at a time from a dropdown; chosen ones show as removable chips. */
export function LanguageSelect({ value, onChange, testPrefix }: { value: string[]; onChange: (v: string[]) => void; testPrefix: string }) {
  const { colors } = useTheme();
  const [open, setOpen] = useState(false);
  const rest = LANG_OPTIONS.filter((o) => !value.includes(o));
  return (
    <View style={{ gap: space.sm }}>
      {value.length ? (
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.sm }}>
          {value.map((o) => (
            <Pressable key={o} testID={`${testPrefix}-selected-${o.toLowerCase()}`} onPress={() => onChange(value.filter((x) => x !== o))} accessibilityLabel={`Remove ${o}`}
              style={[float, { flexDirection: "row", alignItems: "center", gap: 6, minHeight: 36, paddingHorizontal: space.md, borderRadius: radius.pill, backgroundColor: colors.brandTertiary }]}>
              <T size={13} weight="700" color="#fff">{o}</T>
              <Ionicons name="close" size={14} color="#fff" />
            </Pressable>
          ))}
        </View>
      ) : null}
      <Pressable testID={`${testPrefix}-dropdown`} onPress={() => setOpen(!open)} style={{ flexDirection: "row", alignItems: "center", gap: space.sm, minHeight: 52, paddingHorizontal: space.md,
        borderRadius: radius.md, borderWidth: open ? 2 : 1, borderColor: open ? colors.brandTertiary : colors.border, backgroundColor: colors.surfaceSecondary }}>
        <Ionicons name="language-outline" size={20} color={colors.brandTertiary} />
        <T style={{ flex: 1 }} color={colors.muted}>{value.length ? "Add another language" : "Choose a language"}</T>
        <Ionicons name={open ? "chevron-up" : "chevron-down"} size={18} color={colors.muted} />
      </Pressable>
      {open ? (
        <View testID={`${testPrefix}-options`} style={[float, { borderRadius: radius.md, backgroundColor: colors.surfaceSecondary, maxHeight: 260, overflow: "hidden" }]}>
          <ScrollView nestedScrollEnabled>
            {rest.map((o) => (
              <Pressable key={o} testID={`${testPrefix}-${o.toLowerCase()}`} onPress={() => { onChange([...value, o]); setOpen(false); }}
                style={({ pressed }) => ({ minHeight: 46, justifyContent: "center", paddingHorizontal: space.md, backgroundColor: pressed ? colors.accentSoft : "transparent", borderBottomWidth: 1, borderBottomColor: colors.border })}>
                <T weight="600">{o}</T>
              </Pressable>
            ))}
          </ScrollView>
        </View>
      ) : null}
    </View>
  );
}

export function Switch({ value, onChange, testID, disabled }: { value: boolean; onChange: (v: boolean) => void; testID: string; disabled?: boolean }) {
  const { colors } = useTheme();
  return (
    <Pressable testID={testID} role="switch" aria-checked={value} disabled={disabled} onPress={() => onChange(!value)} hitSlop={8}
      style={{ width: 52, height: 30, borderRadius: 15, padding: 3, backgroundColor: value ? colors.success : colors.borderStrong, opacity: disabled ? 0.5 : 1, alignItems: value ? "flex-end" : "flex-start" }}>
      <View style={{ width: 24, height: 24, borderRadius: 12, backgroundColor: "#fff" }} />
    </Pressable>
  );
}
