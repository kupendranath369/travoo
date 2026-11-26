import Ionicons from "@react-native-vector-icons/ionicons";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import React from "react";
import { Pressable, View } from "react-native";
import Animated, { FadeInDown } from "react-native-reanimated";

import { IconName, T, radius, space } from "@/src/components/ui";
import { useTheme } from "@/src/theme";

export type Svc = "rent" | "book";

export const SVC: Record<Svc, { img: any; icon: IconName; title: string; line: string; points: string[] }> = {
  rent: { img: require("@/assets/images/hero-rent-driver.jpg"), icon: "speedometer-outline", title: "Rent a Driver", line: "Have a car? Hire a verified driver for your trip.",
    points: ["Verified & trusted drivers", "Flexible bookings", "Local & outstation trips"] },
  book: { img: require("@/assets/images/hero-book-car.jpg"), icon: "car-sport", title: "Book Car", line: "Don't have a car? Book a car with a driver for your journey.",
    points: ["Car + Driver in one booking", "Multiple vehicle options", "For local & outstation travel"] },
};

const navyFade = ["rgba(14,42,79,0)", "rgba(14,42,79,0.55)", "rgba(14,42,79,0.96)"] as const;

function GoldBadge({ icon, size = 56 }: { icon: IconName; size?: number }) {
  const { colors } = useTheme();
  return (
    <LinearGradient colors={["#E6BE5A", colors.brandSecondary]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
      style={{ width: size, height: size, borderRadius: size * 0.32, alignItems: "center", justifyContent: "center", borderWidth: 2, borderColor: "rgba(255,255,255,0.7)" }}>
      <Ionicons name={icon} size={size * 0.5} color="#FFFFFF" />
    </LinearGradient>
  );
}

export function Points({ items, light, testID }: { items: string[]; light?: boolean; testID?: string }) {
  const { colors } = useTheme();
  return (
    <View testID={testID} style={{ gap: 6 }}>
      {items.map((p) => (
        <View key={p} style={{ flexDirection: "row", alignItems: "center", gap: space.sm }}>
          <Ionicons name="checkmark-circle" size={18} color={colors.brandTertiary} />
          <T size={13} weight="600" color={light ? "#FFFFFF" : colors.onSurface}>{p}</T>
        </View>
      ))}
    </View>
  );
}

/** Photo hero shown at the top of Rent a Driver / Book Car. */
export function ServiceHero({ service }: { service: Svc }) {
  const s = SVC[service];
  return (
    <Animated.View key={service} entering={FadeInDown.duration(450)} testID={`hire-hero-${service}`}
      style={{ height: 270, borderRadius: 28, overflow: "hidden", shadowColor: "#0E2A4F", shadowOpacity: 0.25, shadowRadius: 20, shadowOffset: { width: 0, height: 10 }, elevation: 8 }}>
      <Image source={s.img} style={{ position: "absolute", width: "100%", height: "100%" }} contentFit="cover" transition={250} />
      <LinearGradient colors={navyFade} locations={[0.15, 0.55, 1]} style={{ position: "absolute", width: "100%", height: "100%" }} />
      <View style={{ flex: 1, justifyContent: "flex-end", padding: space.lg, gap: space.sm }}>
        <GoldBadge icon={s.icon} size={52} />
        <T testID="hire-hero-title" size={26} weight="800" color="#FFFFFF">{s.title}</T>
        <T size={13} color="rgba(255,255,255,0.88)">{s.line}</T>
        <Points items={s.points} light />
      </View>
    </Animated.View>
  );
}

/** Large photo card on the service chooser. */
export function ServiceChoiceCard({ service, onPress, delay = 0 }: { service: Svc; onPress: () => void; delay?: number }) {
  const { colors } = useTheme();
  const s = SVC[service];
  return (
    <Animated.View entering={FadeInDown.delay(delay).duration(450)}>
      <Pressable testID={`hire-choose-${service}`} onPress={onPress}
        style={({ pressed }) => ({ borderRadius: 28, backgroundColor: colors.surfaceSecondary, overflow: "hidden", transform: [{ scale: pressed ? 0.98 : 1 }],
          shadowColor: "#0E2A4F", shadowOpacity: 0.12, shadowRadius: 18, shadowOffset: { width: 0, height: 8 }, elevation: 5 })}>
        <View style={{ height: 170 }}>
          <Image source={s.img} style={{ width: "100%", height: "100%" }} contentFit="cover" />
          <LinearGradient colors={["rgba(250,246,238,0)", colors.surfaceSecondary]} locations={[0.55, 1]} style={{ position: "absolute", width: "100%", height: "100%" }} />
        </View>
        <View style={{ alignItems: "center", marginTop: -34 }}><GoldBadge icon={s.icon} size={64} /></View>
        <View style={{ padding: space.lg, paddingTop: space.sm, gap: space.md }}>
          <View style={{ alignItems: "center", gap: 4 }}>
            <T size={22} weight="800" center>{s.title}</T>
            <T size={13} color={colors.muted} center>{s.line}</T>
          </View>
          <Points items={s.points} />
          <PremiumButton testID={`hire-choose-${service}-cta`} label={s.title} gold={service === "book"} onPress={onPress} />
        </View>
      </Pressable>
    </Animated.View>
  );
}

/** Pill CTA: navy, or gold gradient. */
export function PremiumButton({ label, onPress, gold, icon = "arrow-forward", loading, testID }: { label: string; onPress: () => void; gold?: boolean; icon?: IconName; loading?: boolean; testID?: string }) {
  const { colors } = useTheme();
  const fill = gold ? (["#E2B651", colors.brandSecondary] as const) : ([colors.brandPrimary, "#1C4275"] as const);
  return (
    <Pressable testID={testID} onPress={onPress} disabled={loading} style={({ pressed }) => ({ transform: [{ scale: pressed ? 0.97 : 1 }], opacity: loading ? 0.7 : 1 })}>
      <LinearGradient colors={fill} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
        style={{ minHeight: 54, borderRadius: radius.pill, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: space.sm, paddingHorizontal: space.xl }}>
        <T size={16} weight="800" color="#FFFFFF">{loading ? "Please wait…" : label}</T>
        <Ionicons name={icon} size={20} color="#FFFFFF" />
      </LinearGradient>
    </Pressable>
  );
}

/** Navy / gold segmented switch between the two services. */
export function ServiceSwitch({ value, onChange }: { value: Svc; onChange: (s: Svc) => void }) {
  const { colors } = useTheme();
  return (
    <View testID="hire-service-switch" style={{ flexDirection: "row", padding: 4, borderRadius: radius.pill, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border }}>
      {(["rent", "book"] as const).map((s) => {
        const on = value === s;
        return (
          <Pressable key={s} testID={`hire-service-tab-${s}`} onPress={() => onChange(s)} style={{ flex: 1, height: 44, borderRadius: radius.pill, overflow: "hidden" }}>
            {on ? <LinearGradient colors={[colors.brandPrimary, "#1C4275"]} style={{ position: "absolute", width: "100%", height: "100%" }} /> : null}
            <View style={{ flex: 1, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6 }}>
              <Ionicons name={SVC[s].icon} size={16} color={on ? colors.brandTertiary : colors.muted} />
              <T weight="700" size={14} color={on ? "#FFFFFF" : colors.onSurface}>{SVC[s].title}</T>
            </View>
          </Pressable>
        );
      })}
    </View>
  );
}

/** White card section with a gold-icon heading. */
export function PremiumSection({ icon, title, children, testID }: { icon: IconName; title: string; children: React.ReactNode; testID?: string }) {
  const { colors } = useTheme();
  return (
    <View testID={testID} style={{ backgroundColor: colors.surfaceSecondary, borderRadius: 24, padding: space.lg, gap: space.md, borderWidth: 1, borderColor: colors.border,
      shadowColor: "#0E2A4F", shadowOpacity: 0.06, shadowRadius: 14, shadowOffset: { width: 0, height: 6 }, elevation: 2 }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: space.sm }}>
        <View style={{ width: 32, height: 32, borderRadius: 10, backgroundColor: colors.accentSoft, alignItems: "center", justifyContent: "center" }}>
          <Ionicons name={icon} size={17} color={colors.brandSecondary} />
        </View>
        <T size={16} weight="800">{title}</T>
      </View>
      {children}
    </View>
  );
}
