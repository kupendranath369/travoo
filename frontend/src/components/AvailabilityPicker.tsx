import Ionicons from "@react-native-vector-icons/ionicons";
import React, { useState } from "react";
import { Modal, Pressable, ScrollView, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Btn, Card, Field, T, radius, space } from "@/src/components/ui";
import { DateField } from "@/src/components/Calendar";
import { useTheme } from "@/src/theme";

export interface AvailabilitySchedule {
  id: string;
  date: string; // ISO date string (YYYY-MM-DD)
  from: string; // HH:MM format
  to: string; // HH:MM format
}

interface AvailabilityPickerProps {
  availability?: AvailabilitySchedule[];
  onChange: (schedules: AvailabilitySchedule[]) => void;
  onSave?: (schedules: AvailabilitySchedule[]) => void;
  saving?: boolean;
}

export function AvailabilityPicker({ availability = [], onChange, onSave, saving }: AvailabilityPickerProps) {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState<AvailabilitySchedule | null>(null);
  const [newDate, setNewDate] = useState<string | null>(null);
  const [newFrom, setNewFrom] = useState("09:00");
  const [newTo, setNewTo] = useState("18:00");
  const [err, setErr] = useState("");
  const testPrefix = "avail"; // Hardcoded for consistency

  const validateTimeRange = (from: string, to: string): boolean => {
    const [fromH, fromM] = from.split(":").map(Number);
    const [toH, toM] = to.split(":").map(Number);
    const fromMinutes = fromH * 60 + fromM;
    const toMinutes = toH * 60 + toM;
    return toMinutes > fromMinutes;
  };

  const checkOverlap = (date: string, from: string, to: string, excludeId?: string): boolean => {
    const [newFromH, newFromM] = from.split(":").map(Number);
    const [newToH, newToM] = to.split(":").map(Number);
    const newFromMinutes = newFromH * 60 + newFromM;
    const newToMinutes = newToH * 60 + newToM;

    return availability.some((schedule) => {
      if (schedule.id === excludeId || schedule.date !== date) return false;
      const [existingFromH, existingFromM] = schedule.from.split(":").map(Number);
      const [existingToH, existingToM] = schedule.to.split(":").map(Number);
      const existingFromMinutes = existingFromH * 60 + existingFromM;
      const existingToMinutes = existingToH * 60 + existingToM;

      // Check for overlap
      return !(newToMinutes <= existingFromMinutes || newFromMinutes >= existingToMinutes);
    });
  };

  const handleAddSchedule = () => {
    setErr("");
    if (!newDate) return setErr("Please select a date");
    if (!newFrom || !newTo) return setErr("Please select start and end times");
    if (!validateTimeRange(newFrom, newTo)) return setErr("End time must be later than start time");
    if (checkOverlap(newDate, newFrom, newTo, editingSchedule?.id)) return setErr("This time slot overlaps with an existing schedule");

    const newSchedule: AvailabilitySchedule = {
      id: editingSchedule?.id || Date.now().toString(),
      date: newDate,
      from: newFrom,
      to: newTo,
    };

    const updated = editingSchedule
      ? availability.map((s) => s.id === editingSchedule.id ? newSchedule : s)
      : [...availability, newSchedule];

    onChange(updated);
    onSave?.(updated);

    setNewDate(null);
    setNewFrom("09:00");
    setNewTo("18:00");
    setEditingSchedule(null);
    setShowAddModal(false);
  };

  const handleEditSchedule = (schedule: AvailabilitySchedule) => {
    setEditingSchedule(schedule);
    setNewDate(schedule.date);
    setNewFrom(schedule.from);
    setNewTo(schedule.to);
    setShowAddModal(true);
  };

  const handleDeleteSchedule = (id: string) => {
    const updated = availability.filter((s) => s.id !== id);
    onChange(updated);
    onSave?.(updated);
  };

  const formatTime = (time: string): string => {
    const [h, m] = time.split(":").map(Number);
    const period = h >= 12 ? "PM" : "AM";
    const hour = h % 12 || 12;
    return `${hour}:${m.toString().padStart(2, "0")} ${period}`;
  };

  const formatDate = (dateStr: string): string => {
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
  };

  return (
    <View style={{ gap: space.md }}>
      <Pressable
        testID={`avail-add-button`}
        onPress={() => {
          setEditingSchedule(null);
          setNewDate(null);
          setNewFrom("09:00");
          setNewTo("18:00");
          setShowAddModal(true);
        }}
        style={{
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "center",
          gap: space.sm,
          padding: space.md,
          backgroundColor: colors.brandPrimary,
          borderRadius: radius.md,
        }}
      >
        <Ionicons name="add-circle" size={20} color={colors.onBrandPrimary} />
        <T weight="700" color={colors.onBrandPrimary}>Add Availability Date</T>
      </Pressable>

      {availability.length > 0 ? (
        <View style={{ gap: space.sm }}>
          {availability.map((schedule) => (
            <Card key={schedule.id} testID={`avail-schedule-${schedule.id}`} style={{
              flexDirection: "row",
              alignItems: "center",
              gap: space.sm,
              padding: space.md,
            }}>
              <View style={{ flex: 1 }}>
                <T weight="700" size={14}>{formatDate(schedule.date)}</T>
                <T size={12} color={colors.muted}>
                  {formatTime(schedule.from)} - {formatTime(schedule.to)}
                </T>
              </View>
              <Pressable
                testID={`avail-edit-${schedule.id}`}
                onPress={() => handleEditSchedule(schedule)}
                hitSlop={8}
                style={{ padding: space.xs }}
              >
                <Ionicons name="pencil" size={18} color={colors.brandPrimary} />
              </Pressable>
              <Pressable
                testID={`avail-delete-${schedule.id}`}
                onPress={() => handleDeleteSchedule(schedule.id)}
                hitSlop={8}
                style={{ padding: space.xs }}
              >
                <Ionicons name="trash" size={18} color={colors.error} />
              </Pressable>
            </Card>
          ))}
        </View>
      ) : (
        <T size={13} color={colors.muted} style={{ textAlign: "center" }}>
          No availability schedules added yet
        </T>
      )}

      {/* Add/Edit Schedule Modal */}
      <Modal visible={showAddModal} animationType="slide" onRequestClose={() => setShowAddModal(false)}>
        <View style={{ flex: 1, backgroundColor: colors.surface, paddingTop: insets.top }}>
          <View style={{
            flexDirection: "row",
            alignItems: "center",
            padding: space.md,
            borderBottomWidth: 1,
            borderBottomColor: colors.border,
          }}>
            <Pressable testID={`avail-modal-close`} onPress={() => setShowAddModal(false)} hitSlop={8} style={{ width: 44, height: 44, alignItems: "center", justifyContent: "center" }}>
              <Ionicons name="close" size={24} color={colors.onSurface} />
            </Pressable>
            <T size={18} weight="800" style={{ flex: 1, textAlign: "center" }}>
              {editingSchedule ? "Edit Availability" : "Add Availability"}
            </T>
            <View style={{ width: 44 }} />
          </View>

          <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: space.lg, gap: space.md }}>
            <DateField
              testID={`avail-date`}
              label="Available Date"
              value={newDate}
              onChange={setNewDate}
              allowClear={false}
              minDate={new Date()} // Prevent past dates
            />

            <Field
              testID={`avail-from`}
              label="Available From"
              value={newFrom}
              onChangeText={setNewFrom}
              placeholder="09:00"
              maxLength={5}
            />

            <Field
              testID={`avail-to`}
              label="Available To"
              value={newTo}
              onChangeText={setNewTo}
              placeholder="18:00"
              maxLength={5}
            />

            {err ? <T color={colors.error} weight="600">{err}</T> : null}

            <Btn
              testID={`avail-save`}
              label={editingSchedule ? "Update Schedule" : "Add Schedule"}
              onPress={handleAddSchedule}
              loading={saving}
              icon="checkmark"
            />
          </ScrollView>
        </View>
      </Modal>
    </View>
  );
}
