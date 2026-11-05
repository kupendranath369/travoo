import { Image } from "expo-image";
import React from "react";
import { View } from "react-native";

const MARK = require("../../assets/images/travoo-mark.png");
const WORD = require("../../assets/images/travoo-wordmark.png");
const FULL = require("../../assets/images/travoo-logo.png");

const MARK_RATIO = 911 / 618;
const WORD_RATIO = 1063 / 388;

/** Official Travoo symbol (passengers, car, road, orange arc & pin). */
export function LogoMark({ size = 48 }: { size?: number }) {
  return <Image testID="travoo-logo-mark" source={MARK} style={{ width: size * MARK_RATIO, height: size }} contentFit="contain" />;
}

/** Horizontal lockup: official symbol + "travoo / Enjoy Your Ride" wordmark. */
export function Logo({ size = 40 }: { size?: number; light?: boolean; tagline?: boolean }) {
  const wh = size * 0.78;
  return (
    <View testID="travoo-logo" style={{ flexDirection: "row", alignItems: "center", gap: size * 0.15 }}>
      <LogoMark size={size} />
      <Image source={WORD} style={{ width: wh * WORD_RATIO, height: wh }} contentFit="contain" />
    </View>
  );
}

/** Full stacked official logo (splash, onboarding). */
export function LogoFull({ width = 220 }: { width?: number }) {
  return <Image testID="travoo-logo-full" source={FULL} style={{ width, height: width * (1005 / 1063) }} contentFit="contain" />;
}
