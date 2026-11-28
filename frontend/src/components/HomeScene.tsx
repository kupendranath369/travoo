import Ionicons from "@react-native-vector-icons/ionicons";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import React, { useEffect } from "react";
import { useWindowDimensions, View } from "react-native";
import Animated, { Easing, useAnimatedStyle, useSharedValue, withRepeat, withSequence, withTiming } from "react-native-reanimated";
import Svg, { Path } from "react-native-svg";

const NAVY = "#0B2240";
const GOLD = "#E9A81F";
const ROAD = 34;

function useLoop(to: number, duration: number) {
  const v = useSharedValue(0);
  useEffect(() => {
    v.value = withRepeat(withTiming(to, { duration, easing: Easing.linear }), -1);
  }, [v, to, duration]);
  return v;
}

/** Animated scene: a family travelling in a car along a hill road. */
export function TravelScene({ height }: { height: number }) {
  const { width } = useWindowDimensions();
  const road = useLoop(70, 600);
  const hills = useLoop(width, 16000);
  const clouds = useLoop(width + 160, 22000);
  const bob = useSharedValue(0);
  useEffect(() => {
    bob.value = withRepeat(withSequence(withTiming(-2.5, { duration: 220 }), withTiming(0, { duration: 220 })), -1);
  }, [bob]);
  const dashes = useAnimatedStyle(() => ({ transform: [{ translateX: road.value - 70 }] }));
  const hillsSt = useAnimatedStyle(() => ({ transform: [{ translateX: hills.value - width }] }));
  const cloudSt = useAnimatedStyle(() => ({ transform: [{ translateX: clouds.value - 160 }] }));
  const carSt = useAnimatedStyle(() => ({ transform: [{ translateY: bob.value }] }));
  const carW = Math.min(230, width * 0.56);
  const hill = `M0 60 Q ${width * 0.15} 10 ${width * 0.3} 45 T ${width * 0.6} 35 T ${width} 50 L ${width} 90 L 0 90 Z`;
  return (
    <View testID="home-travel-scene" pointerEvents="none" style={{ position: "absolute", left: 0, right: 0, top: 0, height, overflow: "hidden" }}>
      <LinearGradient colors={["#EEF1F4", "#E3EBF0", "#D5E6DD"]} style={{ position: "absolute", width: "100%", height: "100%" }} />
      <View style={{ position: "absolute", right: 36, top: height * 0.32, width: 46, height: 46, borderRadius: 23, backgroundColor: "#F2C46D", opacity: 0.85 }} />
      <Animated.View style={[{ position: "absolute", top: height * 0.26, flexDirection: "row", gap: 120 }, cloudSt]}>
        <Ionicons name="cloud" size={34} color="#FFFFFF" />
        <Ionicons name="cloud" size={24} color="#FFFFFF" style={{ marginTop: 18 }} />
      </Animated.View>
      <Animated.View style={[{ position: "absolute", bottom: ROAD - 4, flexDirection: "row", width: width * 2 }, hillsSt]}>
        {[0, 1].map((i) => (
          <Svg key={i} width={width} height={90}>
            <Path d={hill} fill={GOLD} opacity={0.35} />
            <Path d={`M0 80 Q ${width * 0.25} 40 ${width * 0.5} 70 T ${width} 65 L ${width} 90 L 0 90 Z`} fill={NAVY} opacity={0.18} />
          </Svg>
        ))}
      </Animated.View>
      <View testID="home-scene-road" style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: ROAD, backgroundColor: NAVY, overflow: "hidden" }}>
        <View style={{ height: 3, backgroundColor: GOLD }} />
        <Animated.View style={[{ position: "absolute", top: ROAD / 2, flexDirection: "row", gap: 35, width: width + 140 }, dashes]}>
          {Array.from({ length: Math.ceil(width / 70) + 3 }).map((_, i) => <View key={i} style={{ width: 35, height: 4, borderRadius: 2, backgroundColor: GOLD }} />)}
        </Animated.View>
      </View>
      <Animated.View style={[{ position: "absolute", bottom: ROAD - 10, right: width * 0.08, width: carW, aspectRatio: 900 / 501 }, carSt]}>
        <Image testID="home-family-car" source={require("@/assets/images/family-car.png")} style={{ width: "100%", height: "100%" }} contentFit="contain" accessibilityLabel="Family travelling in a car" />
      </Animated.View>
    </View>
  );
}

/** Gold steering wheel drawn in SVG. */
export function SteeringWheel({ size, color = GOLD }: { size: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 100 100">
      <Path d="M50 6a44 44 0 1 0 0.01 0Z M50 18a32 32 0 1 1 -0.01 0Z" fill={color} fillRule="evenodd" />
      <Path d="M50 40a10 10 0 1 0 0.01 0Z" fill={color} />
      <Path d="M20 46 Q50 36 80 46 L80 54 Q62 50 56 56 L44 56 Q38 50 20 54 Z M45 58 L55 58 L58 84 L42 84 Z" fill={color} />
    </Svg>
  );
}

/** Home service tile: simple navy card with the service name. */
export function ServiceTile({ kind, title, sub }: { kind: "rent" | "book"; title: string; sub: string }) {
  return (
    <View style={{ flex: 1, borderRadius: 16, backgroundColor: NAVY, borderWidth: 1.5, borderColor: GOLD, overflow: "hidden", alignItems: "center", justifyContent: "center",
      paddingVertical: 14, paddingHorizontal: 8, shadowColor: NAVY, shadowOpacity: 0.18, shadowRadius: 8, shadowOffset: { width: 0, height: 4 }, elevation: 3 }}>
      <View testID={`home-tile-${kind}`} style={{ alignItems: "center", gap: 4 }}>
        <Animated.Text numberOfLines={1} style={{ fontFamily: "PJS-Bold", fontSize: 17, letterSpacing: 0.3, color: "#FFFFFF" }}>{title}</Animated.Text>
        <View style={{ width: 22, height: 2, borderRadius: 1, backgroundColor: GOLD }} />
        <Animated.Text numberOfLines={1} style={{ fontFamily: "PJS-Regular", fontSize: 13, color: "#E9D6AE" }}>{sub}</Animated.Text>
      </View>
    </View>
  );
}

/** Animated Rent a Driver scene: swaying steering wheel over a moving road. */
export function RentDriverScene() {
  const road = useLoop(70, 500);
  const sway = useSharedValue(0);
  const glow = useSharedValue(0.25);
  useEffect(() => {
    sway.value = withRepeat(withSequence(withTiming(-22, { duration: 1300, easing: Easing.inOut(Easing.quad) }), withTiming(18, { duration: 1500, easing: Easing.inOut(Easing.quad) })), -1, true);
    glow.value = withRepeat(withTiming(0.5, { duration: 1400 }), -1, true);
  }, [sway, glow]);
  const wheel = useAnimatedStyle(() => ({ transform: [{ rotate: `${sway.value}deg` }] }));
  const glowSt = useAnimatedStyle(() => ({ opacity: glow.value }));
  const dashes = useAnimatedStyle(() => ({ transform: [{ translateY: road.value - 70 }] }));
  return (
    <View testID="rent-driver-scene" pointerEvents="none" style={{ position: "absolute", width: "100%", height: "100%", backgroundColor: NAVY, overflow: "hidden" }}>
      <LinearGradient colors={["#1E3554", NAVY, "#0D1828"]} style={{ position: "absolute", width: "100%", height: "100%" }} />
      <View style={{ position: "absolute", left: "50%", marginLeft: -60, top: 0, bottom: 0, width: 120, overflow: "hidden" }}>
        <Svg width={120} height="100%" viewBox="0 0 120 100" preserveAspectRatio="none" style={{ position: "absolute" }}>
          <Path d="M50 0 L70 0 L120 100 L0 100 Z" fill="#0A1322" opacity={0.7} />
        </Svg>
        <Animated.View style={[{ position: "absolute", left: 57, gap: 30 }, dashes]}>
          {Array.from({ length: 12 }).map((_, i) => <View key={i} style={{ width: 6, height: 40, borderRadius: 3, backgroundColor: GOLD, opacity: 0.7 }} />)}
        </Animated.View>
      </View>
      <View style={{ position: "absolute", right: 18, top: 16, width: 150, height: 150, alignItems: "center", justifyContent: "center" }}>
        <Animated.View style={[{ position: "absolute", width: 150, height: 150, borderRadius: 75, backgroundColor: "rgba(197,160,89,0.22)" }, glowSt]} />
        <Animated.View style={wheel}><SteeringWheel size={118} /></Animated.View>
      </View>
    </View>
  );
}
