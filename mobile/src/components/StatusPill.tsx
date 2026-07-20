import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { colors, radius, spacing } from '../theme';
import type { TourStatus } from '../types';

const LABELS: Record<TourStatus, string> = {
  not_purchased: 'Not purchased',
  purchased: 'Ready to download',
  in_progress: 'Walk in progress',
  completed_locked: 'Completed',
};

const COLORS: Record<TourStatus, string> = {
  not_purchased: colors.textMuted,
  purchased: colors.primary,
  in_progress: colors.success,
  completed_locked: colors.textMuted,
};

export function StatusPill({ status }: { status: TourStatus }) {
  return (
    <View style={[styles.pill, { borderColor: COLORS[status] }]}>
      <Text style={[styles.text, { color: COLORS[status] }]}>{LABELS[status]}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  pill: {
    alignSelf: 'flex-start',
    borderWidth: 1,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
  },
  text: { fontSize: 12, fontWeight: '600' },
});
