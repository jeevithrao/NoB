import React, { useEffect, useState } from 'react';
import { Alert, StyleSheet, Text } from 'react-native';
import * as Location from 'expo-location';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { ScreenContainer } from '../components/ScreenContainer';
import { PrimaryButton } from '../components/PrimaryButton';
import { getDownloadedTour } from '../api/offlineStorage';
import { distanceMeters } from '../api/geo';
import { sessionsApi } from '../api/endpoints';
import { ApiRequestError } from '../api/client';
import { colors, spacing } from '../theme';
import type { AppStackParamList } from '../navigation/types';
import type { DownloadedTour } from '../types';

type Props = NativeStackScreenProps<AppStackParamList, 'RouteToStart'>;

export function RouteToStartScreen({ route, navigation }: Props) {
  const { tourId } = route.params;
  const [tour, setTour] = useState<DownloadedTour | null>(null);
  const [distanceToStart, setDistanceToStart] = useState<number | null>(null);
  const [permissionDenied, setPermissionDenied] = useState(false);
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    (async () => {
      const downloaded = await getDownloadedTour(tourId);
      if (!downloaded) {
        Alert.alert('Not downloaded', 'Download this tour before starting the walk.');
        navigation.replace('Download', { tourId });
        return;
      }
      setTour(downloaded);

      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        setPermissionDenied(true);
        return;
      }

      const position = await Location.getCurrentPositionAsync({});
      const firstStop = downloaded.tourPackage.stops[0];
      setDistanceToStart(
        distanceMeters(
          position.coords.latitude,
          position.coords.longitude,
          parseFloat(firstStop.lat),
          parseFloat(firstStop.lng)
        )
      );
    })();
  }, [tourId]);

  async function handleStartWalk() {
    setStarting(true);
    try {
      const session = await sessionsApi.createOrResume(tourId);
      navigation.replace('ActiveWalk', { tourId, sessionId: session.id });
    } catch (err) {
      const message = err instanceof ApiRequestError ? err.message : 'Could not start the walk.';
      Alert.alert('Unable to start', message);
    } finally {
      setStarting(false);
    }
  }

  if (!tour) return null;

  const firstStop = tour.tourPackage.stops[0];

  return (
    <ScreenContainer style={styles.center}>
      <Text style={styles.title}>Head to the start</Text>
      <Text style={styles.stopName}>{firstStop.name}</Text>

      {permissionDenied ? (
        <Text style={styles.text}>
          Location permission is needed so the app can tell when you\u2019ve arrived at each stop.
          Enable it in Settings and come back.
        </Text>
      ) : distanceToStart !== null ? (
        <Text style={styles.text}>
          You\u2019re about {Math.round(distanceToStart)} m from the starting point.
        </Text>
      ) : (
        <Text style={styles.text}>Getting your location\u2026</Text>
      )}

      <PrimaryButton
        title="I've arrived \u2014 start the walk"
        onPress={handleStartWalk}
        loading={starting}
        disabled={permissionDenied}
        style={styles.button}
      />
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  center: { justifyContent: 'center', alignItems: 'center' },
  title: { color: colors.text, fontSize: 22, fontWeight: '800', textAlign: 'center' },
  stopName: { color: colors.primary, fontSize: 16, fontWeight: '700', marginTop: spacing.sm, marginBottom: spacing.lg },
  text: { color: colors.textMuted, fontSize: 14, textAlign: 'center', marginBottom: spacing.xl },
  button: { alignSelf: 'stretch' },
});
