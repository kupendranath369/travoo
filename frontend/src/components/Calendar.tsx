import Ionicons from "@react-native-vector-icons/ionicons";
import React, { useMemo, useState } from "react";
import { Modal, Pressable, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { isoDate } from "@/src/components/DateChips";
import { Btn, T, radius, space } from "@/src/components/ui";
import { useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

/** Month-grid calendar in a bottom sheet. Past dates are disabled; `marked` dates show a dot (e.g. days with rides). */
export function DateField({ label, value, onChange, marked, allowClear, testID }: { label: string; value: string | null; onChange: (d: string | null) => void; marked?: Set<string>; allowClear?: boolean; testID: string }) {
  const { colors } = useTheme();
  const { t, fmtDate } = useI18n();
  const insets = useSafeAreaInsets();
  const [open, setOpen] = useState(false);
  const today = isoDate(new Date());
  const [cursor, setCursor] = useState(() => {
    const d = value ? new Date(`${value}T00:00:00`) : new Date();
    return new Date(d.getFullYear(), d.getMonth(), 1);
  });
  const days = useMemo(() => {
    const first = (cursor.getDay() + 6) % 7; // Monday first
    const n = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0).getDate();
    return [...Array(first).fill(null), ...Array.from({ length: n }, (_, i) => isoDate(new Date(cursor.getFullYear(), cursor.getMonth(), i + 1)))];
  }, [cursor]);
  const dayNames = t("v2.days").split(",");
  const minMonth = new Date(new Date().getFullYear(), new Date().getMonth(), 1);

  return (
    <>
      <Pressable testID={testID} onPress={() => setOpen(true)} style={{ flexDirection: "row", alignItems: "center", gap: space.md, minHeight: 56 }}>
        <Ionicons name="calendar-outline" size={20} color={colors.brandPrimary} />
        <View style={{ flex: 1 }}>
          <T size={12} color={colors.muted}>{label}</T>
          <T testID={`${testID}-value`} size={15} weight="700">{value ? fmtDate(value, { weekday: "short", day: "numeric", month: "short", year: "numeric" }) : t("search.any_date")}</T>
        </View>
        <Ionicons name="chevron-down" size={18} color={colors.muted} />
      </Pressable>
      <Modal visible={open} transparent animationType="slide" onRequestClose={() => setOpen(false)}>
        <Pressable style={{ flex: 1, backgroundColor: colors.scrim }} onPress={() => setOpen(false)} />
        <View testID={`${testID}-calendar`} style={{ backgroundColor: colors.surfaceSecondary, borderTopLeftRadius: radius.lg, borderTopRightRadius: radius.lg, padding: space.lg, paddingBottom: insets.bottom + space.lg, gap: space.md }}>
          <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
            <Pressable testID={`${testID}-prev`} disabled={cursor <= minMonth} hitSlop={10} onPress={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1))} style={{ opacity: cursor <= minMonth ? 0.3 : 1 }}>
              <Ionicons name="chevron-back" size={24} color={colors.onSurface} />
            </Pressable>
            <T size={16} weight="800">{fmtDate(isoDate(cursor), { month: "long", year: "numeric" })}</T>
            <Pressable testID={`${testID}-next`} hitSlop={10} onPress={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1))}>
              <Ionicons name="chevron-forward" size={24} color={colors.onSurface} />
            </Pressable>
          </View>
          <View style={{ flexDirection: "row" }}>
            {dayNames.map((d) => <T key={d} size={12} weight="700" color={colors.muted} center style={{ flex: 1 }}>{d}</T>)}
          </View>
          <View style={{ flexDirection: "row", flexWrap: "wrap" }}>
            {days.map((d, i) => {
              const past = !!d && d < today;
              const sel = d === value;
              return (
                <View key={i} style={{ width: `${100 / 7}%`, aspectRatio: 1, padding: 2 }}>
                  {d ? (
                    <Pressable testID={`${testID}-day-${d}`} disabled={past} onPress={() => { onChange(d); setOpen(false); }} style={{ flex: 1, borderRadius: radius.pill, alignItems: "center", justifyContent: "center", backgroundColor: sel ? colors.brandPrimary : d === today ? colors.brandSoft : "transparent", opacity: past ? 0.3 : 1 }}>
                      <T weight={sel ? "800" : "500"} color={sel ? colors.onBrandPrimary : colors.onSurface}>{Number(d.slice(8))}</T>
                      {marked?.has(d) ? <View style={{ width: 5, height: 5, borderRadius: 3, backgroundColor: sel ? colors.onBrandPrimary : colors.brandTertiary, marginTop: 1 }} /> : null}
                    </Pressable>
                  ) : null}
                </View>
              );
            })}
          </View>
          {marked ? <T size={12} color={colors.muted}>● {t("v2.rides_on_day")}</T> : null}
          {allowClear ? <Btn small variant="ghost" label={t("search.any_date")} onPress={() => { onChange(null); setOpen(false); }} testID={`${testID}-any`} /> : null}
        </View>
      </Modal>
    </>
  );
}
