import React, { useCallback, useState } from 'react';
import { FlatList, RefreshControl, StyleSheet, Text, View, Pressable } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { ScreenContainer } from '../components/ScreenContainer';
import { TourCard } from '../components/TourCard';
import { toursApi } from '../api/endpoints';
import { useAuth } from '../context/AuthContext';
import { colors, spacing } from '../theme';
import type { AppStackParamList } from '../navigation/types';
import type { TourListItem } from '../types';

type Props = NativeStackScreenProps<AppStackParamList, 'Home'>;

export function HomeFeedScreen({ navigation }: Props) {
  const { user } = useAuth();
  const [tours, setTours] = useState<TourListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await toursApi.list('Bangalore');
      setTours(data);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  // Refetch every time the screen regains focus so status (e.g. just
  // completed a walk) is always current without a manual pull-to-refresh.
  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  return (
    <ScreenContainer>
      <View style={styles.header}>
        <View>
          <Text style={styles.greeting}>Namaskara{user?.full_name ? `, ${user.full_name.split(' ')[0]}` : ''}</Text>
          <Text style={styles.subtitle}>Bangalore</Text>
        </View>
        <Pressable onPress={() => navigation.navigate('Profile')} style={styles.avatarButton}>
          <Text style={styles.avatarInitial}>{(user?.full_name || user?.email || '?')[0].toUpperCase()}</Text>
        </Pressable>
      </View>

      <FlatList
        data={tours}
        keyExtractor={(item) => item.id}
        contentContainerStyle={{ paddingBottom: spacing.xl }}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => {
              setRefreshing(true);
              load();
            }}
            tintColor={colors.primary}
          />
        }
        ListEmptyComponent={
          !loading ? <Text style={styles.empty}>No tours available yet.</Text> : null
        }
        renderItem={({ item }) => (
          <TourCard tour={item} onPress={() => navigation.navigate('TourDetail', { tourId: item.id })} />
        )}
      />
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  greeting: { color: colors.text, fontSize: 22, fontWeight: '800' },
  subtitle: { color: colors.textMuted, fontSize: 14, marginTop: 2 },
  avatarButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.surfaceAlt,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: colors.border,
  },
  avatarInitial: { color: colors.primary, fontWeight: '700' },
  empty: { color: colors.textMuted, textAlign: 'center', marginTop: spacing.xl },
});
