import React from 'react';
import { StyleSheet, Text } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { ScreenContainer } from '../components/ScreenContainer';
import { PrimaryButton } from '../components/PrimaryButton';
import { useAuth } from '../context/AuthContext';
import { colors, spacing } from '../theme';
import type { AppStackParamList } from '../navigation/types';

type Props = NativeStackScreenProps<AppStackParamList, 'Profile'>;

export function ProfileScreen({ navigation }: Props) {
  const { user, logout } = useAuth();

  return (
    <ScreenContainer>
      <Text style={styles.name}>{user?.full_name || 'Wanderer'}</Text>
      <Text style={styles.email}>{user?.email}</Text>

      <PrimaryButton
        title="Log out"
        variant="danger"
        onPress={async () => {
          await logout();
        }}
        style={styles.button}
      />
      <PrimaryButton title="Back" variant="secondary" onPress={() => navigation.goBack()} style={styles.button} />
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  name: { color: colors.text, fontSize: 22, fontWeight: '800', marginTop: spacing.lg },
  email: { color: colors.textMuted, fontSize: 14, marginTop: spacing.xs, marginBottom: spacing.xl },
  button: { marginTop: spacing.md },
});
