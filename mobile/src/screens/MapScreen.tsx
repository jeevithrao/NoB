import React, { useEffect, useState } from 'react';
import { StyleSheet, Text, View, ActivityIndicator, FlatList } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import * as Location from 'expo-location';
import { ScreenContainer } from '../components/ScreenContainer';
import { getDownloadedTour } from '../api/offlineStorage';
import { colors, spacing } from '../theme';
import type { AppStackParamList } from '../navigation/types';
import type { DownloadedTour, StopWithAudio } from '../types';

type Props = NativeStackScreenProps<AppStackParamList, 'MapScreen'>;

export function MapScreen({ route }: Props) {
  const { tourId } = route.params;
  const [tour, setTour] = useState<DownloadedTour | null>(null);
  const [userLocation, setUserLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const downloaded = await getDownloadedTour(tourId);
        setTour(downloaded);

        const { status } = await Location.requestForegroundPermissionsAsync();
        if (status === 'granted') {
          const loc = await Location.getCurrentPositionAsync({});
          setUserLocation({ lat: loc.coords.latitude, lng: loc.coords.longitude });
        }
      } catch (err) {
        console.error('Failed to load map data', err);
      } finally {
        setLoading(false);
      }
    })();
  }, [tourId]);

  if (loading) {
    return (
      <ScreenContainer style={styles.center}>
        <ActivityIndicator size="large" color={colors.primary} />
      </ScreenContainer>
    );
  }

  const stops = tour?.tourPackage.stops || [];

  return (
    <ScreenContainer>
      <View style={styles.headerContainer}>
        <Text style={styles.tourTitle}>{tour?.tourPackage.name || 'Tour Map'}</Text>
        <Text style={styles.subtitle}>
          {userLocation
            ? `Your location: ${userLocation.lat.toFixed(4)}, ${userLocation.lng.toFixed(4)}`
            : 'Locating...'}
        </Text>
      </View>

      <FlatList
        data={stops}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.listContent}
        renderItem={({ item, index }) => (
          <View style={styles.stopCard}>
            <View style={styles.pinBadge}>
              <Text style={styles.pinText}>{index + 1}</Text>
            </View>
            <View style={styles.stopDetails}>
              <Text style={styles.stopName}>{item.name}</Text>
              <Text style={styles.stopCoords}>
                📍 {item.lat.toFixed(4)}, {item.lng.toFixed(4)} • Radius: {item.trigger_radius_m}m
              </Text>
              <Text style={styles.narrativeSnippet} numberOfLines={2}>
                {item.narrative_text}
              </Text>
            </View>
          </View>
        )}
      />
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  center: { justifyContent: 'center', alignItems: 'center' },
  headerContainer: { paddingVertical: spacing.md, borderBottomWidth: 1, borderBottomColor: colors.border },
  tourTitle: { fontSize: 20, fontWeight: '700', color: colors.text },
  subtitle: { fontSize: 13, color: colors.textMuted, marginTop: spacing.xs },
  listContent: { paddingTop: spacing.md, paddingBottom: spacing.xl },
  stopCard: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    padding: spacing.md,
    borderRadius: 12,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  pinBadge: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justify: 'center',
    marginRight: spacing.md,
  },
  pinText: { color: colors.background, fontWeight: 'bold', fontSize: 14 },
  stopDetails: { flex: 1 },
  stopName: { fontSize: 16, fontWeight: '600', color: colors.text },
  stopCoords: { fontSize: 12, color: colors.textMuted, marginTop: 2 },
  narrativeSnippet: { fontSize: 13, color: colors.textMuted, marginTop: spacing.xs },
});
