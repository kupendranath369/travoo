import { Image } from "expo-image";
import React, { useEffect } from "react";
import { ViewStyle } from "react-native";
import Animated, { Easing, useAnimatedStyle, useSharedValue, withDelay, withRepeat, withSequence, withTiming } from "react-native-reanimated";

/** Gently floating picture (loops up and down). */
export function FloatingImage({ uri, source, style, delay = 0, testID, accessibilityLabel }: { uri?: string; source?: number; style?: ViewStyle; delay?: number; testID?: string; accessibilityLabel?: string }) {
  const y = useSharedValue(0);
  useEffect(() => {
    y.value = withDelay(delay, withRepeat(withSequence(withTiming(-6, { duration: 1400, easing: Easing.inOut(Easing.quad) }), withTiming(0, { duration: 1400, easing: Easing.inOut(Easing.quad) })), -1));
  }, [delay, y]);
  const st = useAnimatedStyle(() => ({ transform: [{ translateY: y.value }] }));
  return (
    <Animated.View testID={testID} accessibilityLabel={accessibilityLabel} style={[style, st]}>
      <Image source={source ?? { uri }} style={{ width: "100%", height: "100%" }} contentFit="contain" />
    </Animated.View>
  );
}

/** Same gentle float for any content. */
export function FloatingView({ children, delay = 0, testID }: { children: React.ReactNode; delay?: number; testID?: string }) {
  const y = useSharedValue(0);
  useEffect(() => {
    y.value = withDelay(delay, withRepeat(withSequence(withTiming(-5, { duration: 1400, easing: Easing.inOut(Easing.quad) }), withTiming(0, { duration: 1400, easing: Easing.inOut(Easing.quad) })), -1));
  }, [delay, y]);
  const st = useAnimatedStyle(() => ({ transform: [{ translateY: y.value }] }));
  return <Animated.View testID={testID} style={st}>{children}</Animated.View>;
}
