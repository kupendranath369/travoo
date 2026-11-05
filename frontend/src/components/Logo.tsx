import Ionicons from "@react-native-vector-icons/ionicons";
import React from "react";
import { View } from "react-native";

import { T } from "@/src/components/ui";
import { useTheme } from "@/src/theme";

/** Travoo brand mark (vector recreation: blue passenger circle, car, orange motion arc & pin).
 *  Swap for the official logo artwork once the image file is uploaded. */
export function LogoMark({ size = 48 }: { size?: number }) {
  const { colors } = useTheme();
  return (
    <View style={{ width: size, height: size }}>
      <View style={{ position: "absolute", inset: 0, borderRadius: size / 2, borderWidth: size * 0.06, borderColor: colors.brandTertiary, borderBottomColor: "transparent", borderLeftColor: "transparent", transform: [{ rotate: "-20deg" }] }} />
      <View style={{ position: "absolute", top: size * 0.1, left: size * 0.1, width: size * 0.8, height: size * 0.8, borderRadius: size, backgroundColor: colors.brandPrimary, alignItems: "center", justifyContent: "center" }}>
        <Ionicons name="people" size={size * 0.34} color={colors.onBrand} style={{ marginBottom: -size * 0.04 }} />
        <Ionicons name="car-sport" size={size * 0.3} color={colors.onBrand} />
      </View>
      <Ionicons name="location" size={size * 0.34} color={colors.brandTertiary} style={{ position: "absolute", right: -size * 0.06, top: -size * 0.06 }} />
    </View>
  );
}

export function Logo({ size = 40, light = false, tagline = true }: { size?: number; light?: boolean; tagline?: boolean }) {
  const { colors } = useTheme();
  return (
    <View testID="travoo-logo" style={{ flexDirection: "row", alignItems: "center", gap: size * 0.25 }}>
      <LogoMark size={size} />
      <View>
        <T weight="800" size={size * 0.62} color={light ? colors.onBrand : colors.brand} style={{ letterSpacing: 1, lineHeight: size * 0.72, fontFamily: "PJS-ExtraBold" }}>
          TRAV<T weight="800" size={size * 0.62} color={colors.brandTertiary} style={{ fontFamily: "PJS-ExtraBold" }}>OO</T>
        </T>
        {tagline ? (
          <T weight="700" size={Math.max(9, size * 0.22)} color={light ? colors.onBrand : colors.brandPrimary} style={{ letterSpacing: 2, fontFamily: "PJS-Bold" }}>
            ENJOY YOUR RIDE.
          </T>
        ) : null}
      </View>
    </View>
  );
}
