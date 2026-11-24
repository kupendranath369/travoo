import React, { useEffect, useRef } from "react";
import { Animated, PanResponder, Pressable, View } from "react-native";

import { T, radius } from "@/src/components/ui";
import { useTheme } from "@/src/theme";

const W = 148;
const H = 44;
const KNOB = W / 2 - 4;

/** Swipe (or tap) switch: left = NO, right = YES. */
export function YesNoSwipe({ value, onChange, testID }: { value: boolean; onChange: (v: boolean) => void; testID: string }) {
  const { colors } = useTheme();
  const x = useRef(new Animated.Value(value ? 1 : 0)).current;
  const cur = useRef(value);
  cur.current = value;
  const cb = useRef(onChange);
  cb.current = onChange;
  useEffect(() => { Animated.spring(x, { toValue: value ? 1 : 0, useNativeDriver: false, friction: 7 }).start(); }, [value, x]);
  const pan = useRef(PanResponder.create({
    onMoveShouldSetPanResponder: (_, g) => Math.abs(g.dx) > 6,
    onMoveShouldSetPanResponderCapture: (_, g) => Math.abs(g.dx) > 6,
    onPanResponderRelease: (_, g) => {
      if (g.dx > 15 && !cur.current) cb.current(true);
      else if (g.dx < -15 && cur.current) cb.current(false);
    },
  })).current;
  const left = x.interpolate({ inputRange: [0, 1], outputRange: [2, W - KNOB - 2] });
  const bg = x.interpolate({ inputRange: [0, 1], outputRange: [colors.border, colors.brandPrimary] });
  return (
    <Animated.View {...pan.panHandlers} testID={testID} role="switch" aria-checked={value}
      style={{ userSelect: "none", width: W, height: H, borderRadius: radius.pill, backgroundColor: bg, justifyContent: "center" }}>
      <Animated.View style={{ position: "absolute", left, width: KNOB, height: H - 4, borderRadius: radius.pill, backgroundColor: "#fff",
        shadowColor: "#000", shadowOpacity: 0.15, shadowRadius: 4, shadowOffset: { width: 0, height: 1 }, elevation: 2 }} />
      <View style={{ flexDirection: "row" }}>
        <Pressable testID={`${testID}-no`} onPress={() => onChange(false)} style={{ flex: 1, height: H, alignItems: "center", justifyContent: "center" }}>
          <T weight="800" color={value ? colors.onBrandPrimary : colors.onSurface}>NO</T>
        </Pressable>
        <Pressable testID={`${testID}-yes`} onPress={() => onChange(true)} style={{ flex: 1, height: H, alignItems: "center", justifyContent: "center" }}>
          <T weight="800" color={value ? colors.brandPrimary : colors.muted}>YES</T>
        </Pressable>
      </View>
    </Animated.View>
  );
}
