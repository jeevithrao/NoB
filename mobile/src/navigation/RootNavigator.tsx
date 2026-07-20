import React from 'react';
import { ActivityIndicator, StyleSheet, View } from 'react-native';
import { NavigationContainer, DarkTheme } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { useAuth } from '../context/AuthContext';
import { colors } from '../theme';
import { LoginScreen } from '../screens/LoginScreen';
import { SignupScreen } from '../screens/SignupScreen';
import { HomeFeedScreen } from '../screens/HomeFeedScreen';
import { TourDetailScreen } from '../screens/TourDetailScreen';
import { DownloadScreen } from '../screens/DownloadScreen';
import { RouteToStartScreen } from '../screens/RouteToStartScreen';
import { ActiveWalkScreen } from '../screens/ActiveWalkScreen';
import { WalkCompleteScreen } from '../screens/WalkCompleteScreen';
import { ProfileScreen } from '../screens/ProfileScreen';
import type { AppStackParamList, AuthStackParamList } from './types';

const AuthStack = createNativeStackNavigator<AuthStackParamList>();
const AppStack = createNativeStackNavigator<AppStackParamList>();

const navTheme = {
  ...DarkTheme,
  colors: { ...DarkTheme.colors, background: colors.background, card: colors.surface, text: colors.text },
};

function AuthNavigator() {
  return (
    <AuthStack.Navigator screenOptions={{ headerShown: false }}>
      <AuthStack.Screen name="Login" component={LoginScreen} />
      <AuthStack.Screen name="Signup" component={SignupScreen} />
    </AuthStack.Navigator>
  );
}

function AppNavigator() {
  return (
    <AppStack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: colors.surface },
        headerTintColor: colors.text,
        headerShadowVisible: false,
      }}
    >
      <AppStack.Screen name="Home" component={HomeFeedScreen} options={{ headerShown: false }} />
      <AppStack.Screen name="TourDetail" component={TourDetailScreen} options={{ title: '' }} />
      <AppStack.Screen name="Download" component={DownloadScreen} options={{ title: 'Download' }} />
      <AppStack.Screen name="RouteToStart" component={RouteToStartScreen} options={{ title: 'Get ready' }} />
      <AppStack.Screen name="ActiveWalk" component={ActiveWalkScreen} options={{ title: 'Walking', headerBackVisible: false }} />
      <AppStack.Screen name="WalkComplete" component={WalkCompleteScreen} options={{ title: '', headerBackVisible: false }} />
      <AppStack.Screen name="Profile" component={ProfileScreen} options={{ title: 'Profile' }} />
    </AppStack.Navigator>
  );
}

export function RootNavigator() {
  const { isLoading, user } = useAuth();

  if (isLoading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  return <NavigationContainer theme={navTheme}>{user ? <AppNavigator /> : <AuthNavigator />}</NavigationContainer>;
}

const styles = StyleSheet.create({
  loadingContainer: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.background },
});
