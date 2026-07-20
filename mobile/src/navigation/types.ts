export type AuthStackParamList = {
  Login: undefined;
  Signup: undefined;
};

export type AppStackParamList = {
  Home: undefined;
  TourDetail: { tourId: string };
  Download: { tourId: string };
  RouteToStart: { tourId: string };
  ActiveWalk: { tourId: string; sessionId: string };
  WalkComplete: { tourId: string; sessionId: string };
  Profile: undefined;
};
