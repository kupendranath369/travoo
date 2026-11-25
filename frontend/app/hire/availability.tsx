import Ionicons from "@react-native-vector-icons/ionicons";
import { useFocusEffect } from "expo-router";
import React, { useCallback, useState } from "react";
import { Pressable, ScrollView, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { DateField } from "@/src/components/Calendar";
import { ClockTimePicker, formatClock } from "@/src/components/ClockTimePicker";
import { confirmAction } from "@/src/components/LocalDriverParts";
import { float } from "@/src/components/localdriver/parts";
import { useToast } from "@/src/components/toast";
import { Btn, Card, Empty, Header, Loading, T, radius, space } from "@/src/components/ui";
import { useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

type Period = { id?: string; from: string; to: string };
type DT = { date: string | null; time: string };
const split = (iso: string): DT => { const d = new Date(new Date(iso).getTime() + 330 * 60000).toISOString(); return { date: d.slice(0, 10), time: d.slice(11, 16) }; };
const join = (v: DT) => `${v.date}T${v.time}:00+05:30`;

function DateTimeField({ label, value, onChange, open, onToggle, testID }: { label: string; value: DT; onChange: (v: DT) => void; open: boolean; onToggle: () => void; testID: string }) {
  const { colors } = useTheme();
  return (
    <View testID={testID} style={{ gap: space.sm, padding: space.md, borderRadius: radius.lg, backgroundColor: colors.surfaceTertiary }}>
      <T weight="800">{label}</T>
      <DateField testID={`${testID}-date`} label="Date" value={value.date} onChange={(date) => onChange({ ...value, date })} />
      <ClockTimePicker testID={`${testID}-time`} label="Time" value={value.time} onChange={(time) => onChange({ ...value, time })} open={open} onToggle={onToggle} />
    </View>
  );
}

export default function ScheduleAvailability() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { fmtDate } = useI18n();
  const toast = useToast();
  const [list, setList] = useState<Period[] | null>(null);
  const [edit, setEdit] = useState<{ id?: string; from: DT; to: DT } | null>(null);
  const [clock, setClock] = useState<"from" | "to" | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => api("/pro/me").then((r) => setList(r.profile?.availability ?? [])).catch(() => setList([])), []);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  const persist = async (next: Period[], msg: string) => {
    setBusy(true); setErr("");
    try { const r = await api("/pro/settings", { method: "PUT", body: { availability: next } }); setList(r.profile.availability ?? []); setEdit(null); toast(msg); return true; }
    catch (e: any) { setErr(e.message); toast(e.message, "error"); return false; }
    finally { setBusy(false); }
  };
  const save = () => {
    if (!edit?.from.date || !edit.to.date) return setErr("Choose both dates");
    const p = { id: edit.id, from: join(edit.from), to: join(edit.to) };
    if (new Date(p.to) <= new Date(p.from)) return setErr("'Available Until' must be later than 'Available From'");
    if (new Date(p.to) <= new Date()) return setErr("This period is already over");
    persist(edit.id ? (list ?? []).map((x) => (x.id === edit.id ? p : x)) : [...(list ?? []), p], "Availability saved");
  };
  const fmt = (iso: string) => { const v = split(iso); return `${fmtDate(v.date!, { weekday: "short", day: "numeric", month: "short" })} · ${formatClock(v.time)}`; };
  const upcoming = (list ?? []).filter((a) => new Date(a.to) > new Date());
  const tomorrow = new Date(Date.now() + 86400000 + 330 * 60000).toISOString().slice(0, 10);

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <Header title="Schedule Availability" />
      {!list ? <Loading /> : (
        <ScrollView contentContainerStyle={{ padding: space.lg, gap: space.lg, paddingBottom: insets.bottom + space.xxl }}>
          <T size={13} color={colors.muted}>Optional. Going Online is enough for immediate trips. Add periods to get booking requests for future trips even while offline.</T>
          {edit ? (
            <Card testID="avail-form" style={[float, { gap: space.md, borderWidth: 0 }]}>
              <DateTimeField testID="avail-from" label="Available From" value={edit.from} onChange={(from) => setEdit({ ...edit, from })} open={clock === "from"} onToggle={() => setClock(clock === "from" ? null : "from")} />
              <DateTimeField testID="avail-to" label="Available Until" value={edit.to} onChange={(to) => setEdit({ ...edit, to })} open={clock === "to"} onToggle={() => setClock(clock === "to" ? null : "to")} />
              {err ? <T testID="avail-error" color={colors.error}>{err}</T> : null}
              <View style={{ flexDirection: "row", gap: space.sm }}>
                <Btn style={{ flex: 1 }} testID="avail-save" label="Save" loading={busy} onPress={save} />
                <Btn variant="ghost" testID="avail-cancel" label="Cancel" onPress={() => { setEdit(null); setErr(""); }} />
              </View>
            </Card>
          ) : <Btn testID="avail-add-button" icon="add" label="Add availability" onPress={() => { setErr(""); setClock(null); setEdit({ from: { date: tomorrow, time: "08:00" }, to: { date: tomorrow, time: "20:00" } }); }} />}
          <T weight="800">Upcoming availability</T>
          {upcoming.length === 0 ? <Empty icon="calendar-outline" title="No scheduled periods" body="You can still receive requests whenever you are Online." /> : null}
          {upcoming.map((a) => (
            <View key={a.id} testID={`avail-item-${a.id}`} style={[float, { flexDirection: "row", alignItems: "center", gap: space.md, padding: space.md, borderRadius: radius.lg, backgroundColor: colors.surfaceSecondary }]}>
              <Ionicons name="calendar" size={22} color={colors.brandTertiary} />
              <View style={{ flex: 1, gap: 2 }}>
                <T size={13} weight="700">From {fmt(a.from)}</T>
                <T size={13} weight="700">Until {fmt(a.to)}</T>
              </View>
              <Pressable testID={`avail-edit-${a.id}`} hitSlop={10} onPress={() => { setErr(""); setClock(null); setEdit({ id: a.id, from: split(a.from), to: split(a.to) }); }}><Ionicons name="create-outline" size={20} color={colors.muted} /></Pressable>
              <Pressable testID={`avail-delete-${a.id}`} hitSlop={10} onPress={() => confirmAction("Delete this period?", "You will stop getting scheduled requests for it.", () => persist((list ?? []).filter((x) => x.id !== a.id), "Deleted"))}>
                <Ionicons name="trash-outline" size={20} color={colors.error} />
              </Pressable>
            </View>
          ))}
        </ScrollView>
      )}
    </View>
  );
}
