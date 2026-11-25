import Ionicons from "@react-native-vector-icons/ionicons";
import React from "react";
import { Text, View } from "react-native";

import { useTheme } from "@/src/theme";

export const IMG = {
  splash: "https://static.prod-images.emergentagent.com/jobs/8861967f-87dd-44ec-b25c-0477aae62e47/images/f74c3d700280347d5382e8f192406fc0d7bd2030a7e669db5040b8e540eba608.jpeg",
  header: "https://static.prod-images.emergentagent.com/jobs/8861967f-87dd-44ec-b25c-0477aae62e47/images/ad180fc88f16ea4ddbf1d8ad8db5798d59206ae260bbda474a93662ae7203fe5.jpeg",
  passenger: "https://static.prod-images.emergentagent.com/jobs/8861967f-87dd-44ec-b25c-0477aae62e47/images/82b78f74f737ca5ce04b846f62de5b502a27971ae4e34f70e01402a2c87ddc93.jpeg",
  driver: "https://static.prod-images.emergentagent.com/jobs/8861967f-87dd-44ec-b25c-0477aae62e47/images/71922a61cab6ae957992b1521ec7cb56cc44470306a0e3e22f345d4b87b7707c.jpeg",
};

/** Green map-pin with a car: the Travoo app mark. */
export function BrandPin({ size = 40 }: { size?: number }) {
  const { colors } = useTheme();
  return (
    <View testID="brand-pin" style={{ width: size, height: size * 1.2, alignItems: "center" }}>
      <Ionicons name="location" size={size * 1.2} color={colors.brandPrimary} style={{ position: "absolute", top: 0 }} />
      <View style={{ position: "absolute", top: size * 0.26, width: size * 0.5, height: size * 0.5, borderRadius: size * 0.25, backgroundColor: "#fff", alignItems: "center", justifyContent: "center" }}>
        <Ionicons name="car" size={size * 0.34} color={colors.brandPrimary} />
      </View>
    </View>
  );
}

/** "Travoo" wordmark: bold italic, deep blue (optionally with the pin). */
export function Wordmark({ size = 28, pin = false, color }: { size?: number; pin?: boolean; color?: string }) {
  const { colors } = useTheme();
  return (
    <View testID="brand-wordmark" style={{ flexDirection: "row", alignItems: "center", gap: size * 0.2 }}>
      {pin ? <BrandPin size={size * 0.9} /> : null}
      <Text style={{ fontFamily: "PJS-Bold", fontSize: size, fontStyle: "italic", color: color ?? colors.brand, letterSpacing: -0.5 }}>Travoo</Text>
    </View>
  );
}
