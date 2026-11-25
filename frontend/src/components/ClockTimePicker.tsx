import Ionicons from "@react-native-vector-icons/ionicons";
import React, { useRef, useState } from "react";
import { Pressable, View } from "react-native";
import Animated, { FadeIn, FadeOut } from "react-native-reanimated";

import { T, radius, space } from "@/src/components/ui";
import { useTheme } from "@/src/theme";

const parse = (v: string) => {
  const [hh, mm] = (v || "09:00").split(":").map((x) => parseInt(x, 10) || 0);
  return { h12: hh % 12 === 0 ? 12 : hh % 12, m: mm, pm: hh >= 12 };
};
const to24 = (h12: number, m: number, pm: boolean) => `${String((h12 % 12) + (pm ? 12 : 0)).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
export const formatClock = (v: string) => { const p = parse(v); return `${p.h12}:${String(p.m).padStart(2, "0")} ${p.pm ? "PM" : "AM"}`; };

const PRESETS: [string, string][] = [["06:00", "6 AM"], ["09:00", "9 AM"], ["12:00", "Noon"], ["15:00", "3 PM"], ["18:00", "6 PM"], ["21:00", "9 PM"]];

/** Up/down arrow that repeats while held. */
function Arrow({ dir, onStep, testID }: { dir: "up" | "down"; onStep: () => void; testID: string }) {
  const { colors } = useTheme();
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const stop = () => { if (timer.current) clearInterval(timer.current); timer.current = null; };
  return (
    <Pressable testID={testID} accessibilityLabel={dir === "up" ? "Increase" : "Decrease"} onPress={onStep} onLongPress={() => { timer.current = setInterval(onStep, 120); }} onPressOut={stop} hitSlop={6}
      style={({ pressed }) => ({ width: 64, height: 40, borderRadius: radius.md, alignItems: "center", justifyContent: "center", backgroundColor: pressed ? colors.brandSoft : "transparent" })}>
      <Ionicons name={dir === "up" ? "chevron-up" : "chevron-down"} size={26} color={colors.brandPrimary} />
    </Pressable>
  );
}

function Digit({ value, onUp, onDown, testID }: { value: string; onUp: () => void; onDown: () => void; testID: string }) {
  const { colors } = useTheme();
  return (
    <View style={{ alignItems: "center" }}>
      <Arrow dir="up" onStep={onUp} testID={`${testID}-up`} />
      <View style={{ minWidth: 84, paddingVertical: space.sm, borderRadius: radius.md, backgroundColor: colors.surfaceInverse, alignItems: "center" }}>
        <T testID={testID} size={44} weight="800" color="#fff" style={{ fontVariant: ["tabular-nums"], letterSpacing: 1 }}>{value}</T>
      </View>
      <Arrow dir="down" onStep={onDown} testID={`${testID}-down`} />
    </View>
  );
}

/** Digital time picker (hour : minute + AM/PM, 5-minute steps, quick presets). */
export function ClockTimePicker({ label, value, onChange, open: openProp, onToggle, testID }: { label: string; value: string; onChange: (v: string) => void; open?: boolean; onToggle?: () => void; testID: string }) {
  const { colors } = useTheme();
  const [own, setOwn] = useState(false);
  const open = openProp ?? own;
  const toggle = onToggle ?? (() => setOwn((x) => !x));
  const { h12, m, pm } = parse(value);
  const set = (h: number, mm: number, p: boolean) => onChange(to24(h, mm, p));
  const stepH = (d: number) => set(((h12 - 1 + d + 12) % 12) + 1, m, pm);
  const stepM = (d: number) => set(h12, (Math.round(m / 5) * 5 + d * 5 + 60) % 60, pm);
  return (
    <View style={{ gap: space.xs }}>
      {label ? <T size={13} weight="600" color={colors.muted}>{label}</T> : null}
      <Pressable testID={testID} onPress={toggle} style={{ flexDirection: "row", alignItems: "center", gap: space.sm, padding: space.md, minHeight: 52,
        borderRadius: radius.md, borderWidth: open ? 2 : 1, borderColor: open ? colors.brandPrimary : colors.border, backgroundColor: colors.surfaceSecondary }}>
        <Ionicons name="time-outline" size={20} color={colors.brandPrimary} />
        <T testID={`${testID}-value`} size={18} weight="800" style={{ flex: 1, fontVariant: ["tabular-nums"] }}>{formatClock(value)}</T>
        <Ionicons name={open ? "chevron-up" : "chevron-down"} size={18} color={colors.muted} />
      </Pressable>
      {open ? (
        <Animated.View entering={FadeIn.duration(180)} exiting={FadeOut.duration(120)} testID={`${testID}-clock`}
          style={{ gap: space.md, padding: space.md, borderRadius: radius.lg, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border }}>
          <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "center", gap: space.sm }}>
            <Digit testID={`${testID}-hour`} value={String(h12).padStart(2, "0")} onUp={() => stepH(1)} onDown={() => stepH(-1)} />
            <T size={40} weight="800" color={colors.onSurface}>:</T>
            <Digit testID={`${testID}-minute`} value={String(m).padStart(2, "0")} onUp={() => stepM(1)} onDown={() => stepM(-1)} />
            <View style={{ gap: space.sm, marginLeft: space.sm }}>
              {(["AM", "PM"] as const).map((x) => {
                const on = (x === "PM") === pm;
                return (
                  <Pressable key={x} testID={`${testID}-${x.toLowerCase()}`} onPress={() => set(h12, m, x === "PM")}
                    style={{ width: 56, height: 44, borderRadius: radius.md, alignItems: "center", justifyContent: "center", backgroundColor: on ? colors.brandPrimary : colors.surfaceTertiary }}>
                    <T weight="800" color={on ? "#fff" : colors.onSurface}>{x}</T>
                  </Pressable>
                );
              })}
            </View>
          </View>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.xs, justifyContent: "center" }}>
            {PRESETS.map(([v, l]) => (
              <Pressable key={v} testID={`${testID}-preset-${v.replace(":", "")}`} onPress={() => onChange(v)}
                style={{ paddingHorizontal: space.md, minHeight: 34, justifyContent: "center", borderRadius: radius.pill, backgroundColor: value === v ? colors.brandSoft : colors.surfaceTertiary, borderWidth: 1, borderColor: value === v ? colors.brandPrimary : "transparent" }}>
                <T size={12} weight="700" color={value === v ? colors.brandPrimary : colors.onSurface}>{l}</T>
              </Pressable>
            ))}
          </View>
          <Pressable testID={`${testID}-done`} onPress={toggle} style={{ alignSelf: "stretch", alignItems: "center", paddingVertical: space.sm, borderRadius: radius.pill, backgroundColor: colors.brandPrimary }}>
            <T weight="800" color="#fff">Done · {formatClock(value)}</T>
          </Pressable>
        </Animated.View>
      ) : null}
    </View>
  );
}
