import Ionicons from "@react-native-vector-icons/ionicons";
import * as Haptics from "expo-haptics";
import { Image } from "expo-image";
import { useRouter } from "expo-router";
import React from "react";
import {
  ActivityIndicator,
  Platform,
  Pressable,
  StyleProp,
  Text,
  TextInput,
  TextInputProps,
  TextProps,
  TextStyle,
  View,
  ViewStyle,
} from "react-native";
import Animated, { useAnimatedStyle, useSharedValue, withSpring } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useI18n } from "@/src/i18n";
import { makeStyles, useTheme } from "@/src/theme";

export type IconName = React.ComponentProps<typeof Ionicons>["name"];
export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32, xxxl: 48 };
export const radius = { sm: 6, md: 12, lg: 20, pill: 999 };

const FONT: Record<string, string> = { "400": "PJS-Regular", "500": "PJS-Medium", "600": "PJS-SemiBold", "700": "PJS-Bold", "800": "PJS-ExtraBold" };

type TProps = TextProps & {
  size?: number;
  weight?: "400" | "500" | "600" | "700" | "800";
  color?: string;
  center?: boolean;
};

/** App text: Plus Jakarta Sans for Latin scripts, system native fonts for Indic/Perso-Arabic scripts. */
export function T({ size = 14, weight = "400", color, center, style, ...rest }: TProps) {
  const { colors } = useTheme();
  const { latin, rtl } = useI18n();
  const font: TextStyle = latin ? { fontFamily: FONT[weight] } : { fontWeight: weight };
  return (
    <Text
      {...rest}
      style={[
        { fontSize: size, color: color ?? colors.onSurface, lineHeight: Math.round(size * (latin ? 1.35 : 1.6)) },
        font,
        center ? { textAlign: "center" } : rtl ? { writingDirection: "rtl" } : null,
        style,
      ]}
    />
  );
}

const AnimatedPressable = Animated.createAnimatedComponent(Pressable);

type BtnProps = {
  label: string;
  onPress?: () => void;
  variant?: "primary" | "accent" | "outline" | "ghost" | "danger" | "navy";
  icon?: IconName;
  loading?: boolean;
  disabled?: boolean;
  style?: StyleProp<ViewStyle>;
  testID?: string;
  small?: boolean;
};

export function Btn({ label, onPress, variant = "primary", icon, loading, disabled, style, testID, small }: BtnProps) {
  const { colors } = useTheme();
  const scale = useSharedValue(1);
  const anim = useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));
  const bg = {
    primary: colors.brandPrimary,
    accent: colors.brandTertiary,
    navy: colors.brand,
    outline: "transparent",
    ghost: "transparent",
    danger: colors.error,
  }[variant];
  const fg = variant === "outline" || variant === "ghost" ? colors.brandPrimary : colors.onBrandPrimary;
  return (
    <AnimatedPressable
      testID={testID}
      disabled={disabled || loading}
      onPressIn={() => (scale.value = withSpring(0.97))}
      onPressOut={() => (scale.value = withSpring(1))}
      onPress={() => {
        if (Platform.OS !== "web") Haptics.selectionAsync();
        onPress?.();
      }}
      style={[
        {
          backgroundColor: bg,
          minHeight: small ? 40 : 52,
          paddingHorizontal: small ? space.md : space.lg,
          borderRadius: radius.pill,
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "center",
          gap: space.sm,
          borderWidth: variant === "outline" ? 1.5 : 0,
          borderColor: colors.brandPrimary,
          opacity: disabled ? 0.5 : 1,
        },
        anim,
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={fg} />
      ) : (
        <>
          {icon ? <Ionicons name={icon} size={small ? 16 : 20} color={fg} /> : null}
          <T weight="700" size={small ? 13 : 15} color={fg} numberOfLines={1}>
            {label}
          </T>
        </>
      )}
    </AnimatedPressable>
  );
}

export function Card({ children, style, onPress, testID }: { children: React.ReactNode; style?: StyleProp<ViewStyle>; onPress?: () => void; testID?: string }) {
  const s = useStyles();
  if (onPress)
    return (
      <Pressable testID={testID} onPress={onPress} style={({ pressed }) => [s.card, { opacity: pressed ? 0.85 : 1 }, style]}>
        {children}
      </Pressable>
    );
  return (
    <View testID={testID} style={[s.card, style]}>
      {children}
    </View>
  );
}

export function Field({ label, error, style, ...rest }: TextInputProps & { label?: string; error?: string }) {
  const s = useStyles();
  const { colors } = useTheme();
  const { rtl } = useI18n();
  return (
    <View style={{ gap: space.xs }}>
      {label ? (
        <T size={13} weight="600" color={colors.muted}>
          {label}
        </T>
      ) : null}
      <TextInput
        placeholderTextColor={colors.muted}
        {...rest}
        style={[s.input, rest.multiline ? { minHeight: 90, textAlignVertical: "top", paddingTop: space.md } : null, rtl ? { textAlign: "right" } : null, style]}
      />
      {error ? (
        <T size={12} color={colors.error}>
          {error}
        </T>
      ) : null}
    </View>
  );
}

export function Chip({ label, active, onPress, icon, testID }: { label: string; active?: boolean; onPress?: () => void; icon?: IconName; testID?: string }) {
  const { colors } = useTheme();
  return (
    <Pressable
      testID={testID}
      onPress={onPress}
      style={{
        height: 36,
        flexShrink: 0,
        paddingHorizontal: space.md,
        borderRadius: radius.pill,
        borderWidth: 1,
        borderColor: active ? colors.brandPrimary : colors.border,
        backgroundColor: active ? colors.brandSoft : colors.surfaceSecondary,
        flexDirection: "row",
        alignItems: "center",
        gap: space.xs,
      }}
    >
      {icon ? <Ionicons name={icon} size={15} color={active ? colors.brandPrimary : colors.muted} /> : null}
      <T size={13} weight="600" color={active ? colors.brandPrimary : colors.onSurface} numberOfLines={1}>
        {label}
      </T>
    </Pressable>
  );
}

export function Badge({ label, tone = "info", icon, testID }: { label: string; tone?: "info" | "success" | "warning" | "error" | "accent" | "muted"; icon?: IconName; testID?: string }) {
  const { colors } = useTheme();
  const map = {
    info: [colors.brandSoft, colors.brandPrimary],
    success: [colors.successSoft, colors.success],
    warning: [colors.accentSoft, colors.brandTertiary],
    accent: [colors.brandTertiary, colors.onBrandTertiary],
    error: [colors.accentSoft, colors.error],
    muted: [colors.surfaceTertiary, colors.muted],
  }[tone];
  return (
    <View testID={testID} style={{ flexDirection: "row", alignItems: "center", gap: 4, backgroundColor: map[0], paddingHorizontal: space.sm, paddingVertical: 3, borderRadius: radius.pill, alignSelf: "flex-start" }}>
      {icon ? <Ionicons name={icon} size={12} color={map[1]} /> : null}
      <T size={11} weight="700" color={map[1]}>
        {label}
      </T>
    </View>
  );
}

export function Header({ title, right, back = true, testID }: { title: string; right?: React.ReactNode; back?: boolean; testID?: string }) {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { colors } = useTheme();
  const { rtl } = useI18n();
  return (
    <View testID={testID} style={{ paddingTop: insets.top + space.sm, paddingBottom: space.md, paddingHorizontal: space.lg, backgroundColor: colors.surfaceSecondary, borderBottomWidth: 1, borderBottomColor: colors.border, flexDirection: "row", alignItems: "center", gap: space.md }}>
      {back ? (
        <Pressable testID="header-back-button" onPress={() => (router.canGoBack() ? router.back() : router.replace("/"))} hitSlop={12} style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: colors.surfaceTertiary, alignItems: "center", justifyContent: "center" }}>
          <Ionicons name={rtl ? "arrow-forward" : "arrow-back"} size={20} color={colors.onSurface} />
        </Pressable>
      ) : null}
      <T size={18} weight="700" style={{ flex: 1 }} numberOfLines={1}>
        {title}
      </T>
      {right}
    </View>
  );
}

export function Loading() {
  const { colors } = useTheme();
  return (
    <View testID="loading-indicator" style={{ flex: 1, alignItems: "center", justifyContent: "center", padding: space.xxl }}>
      <ActivityIndicator size="large" color={colors.brandPrimary} />
    </View>
  );
}

export function Empty({ icon = "car-outline", title, body, action }: { icon?: IconName; title: string; body?: string; action?: React.ReactNode }) {
  const { colors } = useTheme();
  return (
    <View testID="empty-state" style={{ alignItems: "center", padding: space.xl, gap: space.sm }}>
      <View style={{ width: 72, height: 72, borderRadius: 36, backgroundColor: colors.brandSoft, alignItems: "center", justifyContent: "center" }}>
        <Ionicons name={icon} size={34} color={colors.brandPrimary} />
      </View>
      <T size={16} weight="700" center>
        {title}
      </T>
      {body ? (
        <T center color={colors.muted}>
          {body}
        </T>
      ) : null}
      {action}
    </View>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const { t } = useI18n();
  return <Empty icon="cloud-offline-outline" title={t("common.error")} body={message} action={onRetry ? <Btn small label={t("common.retry")} onPress={onRetry} testID="retry-button" /> : null} />;
}

export function Avatar({ name, uri, size = 44 }: { name?: string; uri?: string | null; size?: number }) {
  const { colors } = useTheme();
  if (uri) return <Image source={{ uri }} style={{ width: size, height: size, borderRadius: size / 2 }} />;
  const initials = (name || "?").split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();
  return (
    <View style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: colors.brand, alignItems: "center", justifyContent: "center" }}>
      <T weight="700" color={colors.onBrand} size={size * 0.36}>
        {initials}
      </T>
    </View>
  );
}

export function Rating({ value, count }: { value?: number; count?: number }) {
  const { colors } = useTheme();
  const { t } = useI18n();
  if (!count) return <T size={12} color={colors.muted}>{t("ride.new_driver")}</T>;
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 3 }}>
      <Ionicons name="star" size={13} color={colors.brandTertiary} />
      <T size={12} weight="700">
        {value?.toFixed(1)}
      </T>
      <T size={12} color={colors.muted}>
        ({count})
      </T>
    </View>
  );
}

export function Section({ title, children, right }: { title: string; children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <View style={{ gap: space.md }}>
      <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
        <T size={18} weight="800">
          {title}
        </T>
        {right}
      </View>
      {children}
    </View>
  );
}

export function Stepper({ value, min = 1, max = 8, onChange, testID }: { value: number; min?: number; max?: number; onChange: (v: number) => void; testID?: string }) {
  const { colors } = useTheme();
  const btn = (icon: IconName, d: number, id: string) => (
    <Pressable testID={`${testID}-${id}`} onPress={() => onChange(Math.min(max, Math.max(min, value + d)))} style={{ width: 40, height: 40, borderRadius: 20, borderWidth: 1, borderColor: colors.border, alignItems: "center", justifyContent: "center", backgroundColor: colors.surfaceSecondary }}>
      <Ionicons name={icon} size={18} color={colors.brandPrimary} />
    </Pressable>
  );
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: space.md }}>
      {btn("remove", -1, "minus")}
      <T testID={`${testID}-value`} size={18} weight="700" style={{ minWidth: 24, textAlign: "center" }}>
        {value}
      </T>
      {btn("add", 1, "plus")}
    </View>
  );
}

export const statusTone = (s: string): "info" | "success" | "warning" | "error" | "muted" =>
  ({ confirmed: "success", completed: "success", approved: "success", started: "info", scheduled: "info", pending: "warning", under_review: "warning", resubmit: "warning", rejected: "error", cancelled: "error" } as any)[s] ?? "muted";

const useStyles = makeStyles((c) => ({
  card: {
    backgroundColor: c.surfaceSecondary,
    borderRadius: radius.lg,
    padding: space.lg,
    borderWidth: 1,
    borderColor: c.border,
    shadowColor: c.brand,
    shadowOpacity: 0.05,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 4 },
    elevation: 1,
  },
  input: {
    minHeight: 50,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: c.border,
    backgroundColor: c.surfaceSecondary,
    paddingHorizontal: space.md,
    fontSize: 15,
    color: c.onSurface,
  },
}));
