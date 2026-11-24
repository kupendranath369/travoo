import Ionicons from "@react-native-vector-icons/ionicons";
import React, { useState } from "react";
import { Pressable, View } from "react-native";

import { radius, space, T } from "@/src/components/ui";
import { useTheme } from "@/src/theme";

const DIAL = 248;
const KNOB = 40;
const HOURS = [12, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11];
const MINUTES = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55];

const parse = (v: string) => {
  const [h, m] = (v || "09:00").split(":").map(Number);
  return { h12: h % 12 || 12, m: m || 0, pm: h >= 12 };
};
const build = (h12: number, m: number, pm: boolean) => `${String((h12 % 12) + (pm ? 12 : 0)).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
export const formatClock = (v: string) => { const p = parse(v); return `${p.h12}:${String(p.m).padStart(2, "0")} ${p.pm ? "PM" : "AM"}`; };

function Dial({ items, selected, onPick, label, testID }: { items: number[]; selected: number; onPick: (n: number) => void; label: (n: number) => string; testID: string }) {
  const { colors } = useTheme();
  const r = DIAL / 2 - KNOB / 2 - 6;
  const idx = items.indexOf(selected);
  return (
    <View testID={testID} style={{ width: DIAL, height: DIAL, borderRadius: DIAL / 2, backgroundColor: colors.surfaceTertiary ?? "#EAF1FA", alignSelf: "center" }}>
      <View style={{ position: "absolute", left: DIAL / 2 - 4, top: DIAL / 2 - 4, width: 8, height: 8, borderRadius: 4, backgroundColor: colors.brandPrimary }} />
      {idx >= 0 ? (
        <View style={{ position: "absolute", left: DIAL / 2, top: DIAL / 2 - 1, width: r, height: 2, backgroundColor: colors.brandPrimary,
          transformOrigin: "0% 50%", transform: [{ rotate: `${idx * 30 - 90}deg` }] }} />
      ) : null}
      {items.map((n, i) => {
        const a = (i * 30 - 90) * (Math.PI / 180);
        const on = n === selected;
        return (
          <Pressable key={n} testID={`${testID}-${n}`} onPress={() => onPick(n)} hitSlop={4}
            style={{ position: "absolute", left: DIAL / 2 + r * Math.cos(a) - KNOB / 2, top: DIAL / 2 + r * Math.sin(a) - KNOB / 2, width: KNOB, height: KNOB,
              borderRadius: KNOB / 2, alignItems: "center", justifyContent: "center", backgroundColor: on ? colors.brandPrimary : "transparent" }}>
            <T weight={on ? "800" : "600"} color={on ? colors.onBrandPrimary : colors.onSurface}>{label(n)}</T>
          </Pressable>
        );
      })}
    </View>
  );
}

function Seg({ label, on, onPress, testID, big }: { label: string; on: boolean; onPress: () => void; testID: string; big?: boolean }) {
  const { colors } = useTheme();
  return (
    <Pressable testID={testID} onPress={onPress} style={{ paddingHorizontal: big ? space.sm : space.md, paddingVertical: big ? 2 : space.xs, borderRadius: radius.sm,
      backgroundColor: on ? colors.brandPrimary : "transparent" }}>
      <T size={big ? 34 : 14} weight="800" color={on ? colors.onBrandPrimary : colors.onSurface}>{label}</T>
    </Pressable>
  );
}

export function ClockTimePicker({ label, value, onChange, open, onToggle, testID }: { label: string; value: string; onChange: (v: string) => void; open: boolean; onToggle: () => void; testID: string }) {
  const { colors } = useTheme();
  const [mode, setMode] = useState<"h" | "m">("h");
  const { h12, m, pm } = parse(value);
  const set = (nh: number, nm: number, npm: boolean) => onChange(build(nh, nm, npm));
  return (
    <View style={{ gap: space.xs }}>
      <T size={13} weight="600" color={colors.muted}>{label}</T>
      <Pressable testID={testID} onPress={() => { setMode("h"); onToggle(); }} style={{ flexDirection: "row", alignItems: "center", gap: space.sm, padding: space.md,
        borderRadius: radius.md, borderWidth: open ? 2 : 1, borderColor: open ? colors.brandPrimary : colors.border, backgroundColor: "#fff" }}>
        <Ionicons name="time-outline" size={20} color={colors.brandPrimary} />
        <T testID={`${testID}-value`} size={16} weight="700" style={{ flex: 1 }}>{formatClock(value)}</T>
        <Ionicons name={open ? "chevron-up" : "chevron-down"} size={18} color={colors.muted} />
      </Pressable>
      {open ? (
        <View testID={`${testID}-clock`} style={{ gap: space.md, padding: space.md, borderRadius: radius.lg, backgroundColor: "#fff", borderWidth: 1, borderColor: colors.border }}>
          <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "center", gap: space.xs }}>
            <Seg big testID={`${testID}-mode-hour`} label={String(h12)} on={mode === "h"} onPress={() => setMode("h")} />
            <T size={34} weight="800">:</T>
            <Seg big testID={`${testID}-mode-minute`} label={String(m).padStart(2, "0")} on={mode === "m"} onPress={() => setMode("m")} />
            <View style={{ marginLeft: space.md, gap: space.xs }}>
              <Seg testID={`${testID}-am`} label="AM" on={!pm} onPress={() => set(h12, m, false)} />
              <Seg testID={`${testID}-pm`} label="PM" on={pm} onPress={() => set(h12, m, true)} />
            </View>
          </View>
          {mode === "h"
            ? <Dial testID={`${testID}-hour`} items={HOURS} selected={h12} label={String} onPick={(n) => { set(n, m, pm); setMode("m"); }} />
            : <Dial testID={`${testID}-minute`} items={MINUTES} selected={m} label={(n) => String(n).padStart(2, "0")} onPick={(n) => set(h12, n, pm)} />}
          <T size={12} color={colors.muted} center>{mode === "h" ? "Tap an hour" : "Tap the minutes"}</T>
          <Pressable testID={`${testID}-done`} onPress={onToggle} style={{ alignSelf: "flex-end", paddingHorizontal: space.lg, paddingVertical: space.sm, borderRadius: radius.pill, backgroundColor: colors.brandPrimary }}>
            <T weight="800" color={colors.onBrandPrimary}>Done</T>
          </Pressable>
        </View>
      ) : null}
    </View>
  );
}
