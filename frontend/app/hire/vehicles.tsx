import { useFocusEffect } from "expo-router";
import React, { useCallback, useState } from "react";
import { ScrollView, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { VehicleForm } from "@/src/components/localdriver/VehicleForm";
import { VehicleRow } from "@/src/components/localdriver/VehicleRow";
import { useToast } from "@/src/components/toast";
import { Btn, Empty, Header, Loading, T, space } from "@/src/components/ui";
import { useTheme } from "@/src/theme";

/** One shared vehicle list for Carpool and Local Driver; Book a Driver needs a separate admin approval per vehicle. */
export default function MyVehicles() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const toast = useToast();
  const [list, setList] = useState<any[] | null>(null);
  const [form, setForm] = useState<{ v?: any; book: boolean } | null>(null);
  const [busy, setBusy] = useState("");
  const load = useCallback(() => api("/pro/me").then((r) => setList(r.vehicles)).catch(() => setList([])), []);
  useFocusEffect(useCallback(() => { load(); }, [load]));
  const request = async (v: any) => {
    setBusy(v.vehicle_id);
    try { await api(`/vehicles/${v.vehicle_id}/commercial`, { method: "POST" }); toast("Sent to Travoo for Book a Driver approval"); await load(); }
    catch (e: any) { toast(e.message, "error"); setForm({ v, book: true }); }
    setBusy("");
  };
  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <Header title="My Vehicles" />
      {!list ? <Loading /> : (
        <ScrollView contentContainerStyle={{ padding: space.lg, gap: space.md, paddingBottom: insets.bottom + space.xxl }}>
          <T size={13} color={colors.muted}>Shared with Carpool. Hatchback and sedan carry up to 3 passengers; SUV/MUV up to the seats on the RC (max 8), driver not counted.</T>
          {form ? <VehicleForm initial={form.v} forBook={form.book} onCancel={() => setForm(null)} onSaved={() => { setForm(null); toast("Vehicle saved"); load(); }} />
            : <Btn testID="vehicles-add" icon="add" label="Add vehicle" onPress={() => setForm({ book: false })} />}
          {list.length === 0 ? <Empty icon="car-outline" title="No vehicles yet" body="Add a vehicle to offer Book a Driver or publish carpool rides." /> : null}
          {list.map((v) => (
            <View key={v.vehicle_id} style={{ gap: space.xs }}>
              <VehicleRow v={v} onEdit={() => setForm({ v, book: v.commercial_status && v.commercial_status !== "none" })} />
              {["none", "rejected", undefined].includes(v.commercial_status) ? (
                <Btn small variant="outline" testID={`vehicles-request-${v.vehicle_id}`} icon="briefcase-outline" label="Use for Book a Driver" loading={busy === v.vehicle_id} onPress={() => request(v)} />
              ) : null}
            </View>
          ))}
        </ScrollView>
      )}
    </View>
  );
}
