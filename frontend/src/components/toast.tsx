import Ionicons from "@react-native-vector-icons/ionicons";
import React, { createContext, useCallback, useContext, useRef, useState } from "react";
import { View } from "react-native";
import Animated, { FadeInUp, FadeOutUp } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { T, space } from "@/src/components/ui";
import { useTheme } from "@/src/theme";

type Toast = { id: number; text: string; tone: "success" | "error" | "info" };
const ToastCtx = createContext<(text: string, tone?: Toast["tone"]) => void>(() => {});

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toast, setToast] = useState<Toast | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const show = useCallback((text: string, tone: Toast["tone"] = "success") => {
    if (timer.current) clearTimeout(timer.current);
    setToast({ id: Date.now(), text, tone });
    timer.current = setTimeout(() => setToast(null), 3200);
  }, []);
  const bg = toast?.tone === "error" ? colors.error : toast?.tone === "info" ? colors.brand : colors.success;
  return (
    <ToastCtx.Provider value={show}>
      {children}
      {toast ? (
        <View pointerEvents="none" style={{ position: "absolute", top: insets.top + space.sm, left: space.lg, right: space.lg }}>
          <Animated.View key={toast.id} entering={FadeInUp} exiting={FadeOutUp} testID="toast-message" style={{ backgroundColor: bg, borderRadius: 14, padding: space.md, flexDirection: "row", gap: space.sm, alignItems: "center" }}>
            <Ionicons name={toast.tone === "error" ? "alert-circle" : "checkmark-circle"} size={20} color={colors.onSuccess} />
            <T color={colors.onSuccess} weight="600" style={{ flex: 1 }}>
              {toast.text}
            </T>
          </Animated.View>
        </View>
      ) : null}
    </ToastCtx.Provider>
  );
}

export const useToast = () => useContext(ToastCtx);
