import React from 'react';
import { Image, Pressable, StyleSheet, Text, View } from 'react-native';
import { colors, radius, spacing } from '../theme';
import { StatusPill } from './StatusPill';
import type { TourListItem } from '../types';

export function TourCard({ tour, onPress }: { tour: TourListItem; onPress: () => void }) {
  const priceLabel = tour.is_free ? 'Free' : `\u20b9${(tour.price_paise / 100).toFixed(0)}`;

  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.card, pressed && styles.pressed]}>
      {tour.cover_image ? (
        <Image source={{ uri: tour.cover_image }} style={styles.image} />
      ) : (
        <View style={[styles.image, styles.imagePlaceholder]} />
      )}
      <View style={styles.body}>
        <Text style={styles.name} numberOfLines={1}>
          {tour.name}
        </Text>
        <Text style={styles.meta}>
          {tour.duration_min ? `${tour.duration_min} min` : ''}
          {tour.duration_min && tour.distance_km ? ' \u00b7 ' : ''}
          {tour.distance_km ? `${tour.distance_km} km` : ''}
          {' \u00b7 '}
          {priceLabel}
        </Text>
        <View style={styles.footerRow}>
          <StatusPill status={tour.status} />
          <Text style={styles.likes}>\u2665 {tour.like_count}</Text>
        </View>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    overflow: 'hidden',
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  pressed: { opacity: 0.85 },
  image: { width: '100%', height: 140 },
  imagePlaceholder: { backgroundColor: colors.surfaceAlt },
  body: { padding: spacing.md },
  name: { color: colors.text, fontSize: 17, fontWeight: '700' },
  meta: { color: colors.textMuted, fontSize: 13, marginTop: spacing.xs },
  footerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: spacing.sm,
  },
  likes: { color: colors.textMuted, fontSize: 13 },
});
