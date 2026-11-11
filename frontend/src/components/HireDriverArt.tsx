import React, { useEffect } from "react";
import Animated, { Easing, useAnimatedStyle, useSharedValue, withRepeat, withSequence, withTiming } from "react-native-reanimated";
import Svg, { Circle, G, Path, Rect } from "react-native-svg";

import { useTheme } from "@/src/theme";

/** Friendly animated chauffeur illustration for "Hire a Driver": gentle bob + waving hand (UI thread, very light). */
export function HireDriverArt({ size = 40 }: { size?: number }) {
  const { colors } = useTheme();
  const bob = useSharedValue(0);
  const wave = useSharedValue(0);
  useEffect(() => {
    bob.value = withRepeat(withTiming(1, { duration: 1400, easing: Easing.inOut(Easing.sin) }), -1, true);
    wave.value = withRepeat(withSequence(withTiming(1, { duration: 350 }), withTiming(-0.3, { duration: 350 }), withTiming(0, { duration: 300 }), withTiming(0, { duration: 1600 })), -1);
  }, [bob, wave]);
  const body = useAnimatedStyle(() => ({ transform: [{ translateY: -2 * bob.value }] }));
  const hand = useAnimatedStyle(() => ({ transform: [{ rotate: `${wave.value * 22}deg` }] }));
  const skin = "#F2C29B"; // illustration skin tone, same in light and dark
  return (
    <Animated.View style={[{ width: size, height: size }, body]}>
      <Svg width={size} height={size} viewBox="0 0 48 48">
        <Circle cx={24} cy={24} r={23} fill={colors.surfaceSecondary} />
        <Path d="M9 46c1-9 7-14 15-14s14 5 15 14z" fill={colors.brandPrimary} />
        <Path d="M20 32l4 6 4-6z" fill={colors.surfaceSecondary} />
        <Rect x={21} y={26} width={6} height={6} rx={2} fill={skin} />
        <Circle cx={24} cy={20} r={8} fill={skin} />
        <Path d="M15 15c0-4 4-7 9-7s9 3 9 7z" fill={colors.brand} />
        <Rect x={13} y={14} width={22} height={3} rx={1.5} fill={colors.brandTertiary} />
        <Circle cx={21} cy={20} r={1} fill={colors.onSurface} />
        <Circle cx={27} cy={20} r={1} fill={colors.onSurface} />
        <Path d="M21 24c2 1.6 4 1.6 6 0" stroke={colors.onSurface} strokeWidth={1.2} fill="none" strokeLinecap="round" />
      </Svg>
      <Animated.View style={[{ position: "absolute", right: -size * 0.06, top: size * 0.42, width: size * 0.3, height: size * 0.3, transformOrigin: "20% 100%" }, hand]}>
        <Svg width={size * 0.3} height={size * 0.3} viewBox="0 0 14 14">
          <G>
            <Rect x={2} y={6} width={4} height={8} rx={2} fill={colors.brandPrimary} />
            <Circle cx={4} cy={4.5} r={3.4} fill={skin} />
          </G>
        </Svg>
      </Animated.View>
    </Animated.View>
  );
}
