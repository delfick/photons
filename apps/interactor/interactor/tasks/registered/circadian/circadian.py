from datetime import timedelta


class Circadian:
    def __init__(self, location, *, sunrise_at, sunset_at):
        self.location = location
        self.sunset_at = sunset_at
        self.sunrise_at = sunrise_at

    def sunrise(self, date):
        if self.sunrise_at is not None:
            return date.replace(hour=self.sunrise_at[0], minute=self.sunrise_at[1])
        else:
            return self.location.sunrise(date)

    def sunset(self, date):
        if self.sunset_at is not None:
            return date.replace(hour=self.sunset_at[0], minute=self.sunset_at[1])
        else:
            return self.location.sunset(date)

    def change_for(self, now, *, min_kelvin, max_kelvin, min_brightness, max_brightness):
        """
        Return (brightness, kelvin) to apply.

        Heavily based on
        https://github.com/claytonjn/hass-circadian_lighting/blob/ff4854e7b72db62252b10a773163588299e06cdc/custom_components/circadian_lighting/__init__.py

        and
        https://github.com/basnijholt/adaptive-lighting/blob/master/custom_components/adaptive_lighting/switch.py
        """
        yesterday = now - timedelta(days=1)
        tomorrow = now + timedelta(days=1)

        sunrise = self.sunrise(now).timestamp()
        sunset = self.sunset(now).timestamp()
        solar_noon = self.location.noon(now).timestamp()
        solar_midnight = self.location.midnight(now).timestamp()

        now = now.timestamp()

        # after midnight, but before sunrise
        if now < sunrise:
            # Because it's before sunrise (and after midnight) sunset must have happend yesterday
            yesterday_sunset = self.sunset(yesterday).timestamp()
            yesterday_solar_midnight = self.location.midnight(yesterday).timestamp()
            if solar_midnight > sunset and yesterday_solar_midnight > yesterday_sunset:
                # Solar midnight is after sunset so use yesterdays time
                solar_midnight = yesterday_solar_midnight

        # after sunset, but before midnight
        elif now > sunset:
            # Because it's after sunset (and before midnight) sunrise should happen tomorrow
            tomorrow_solar_midnight = self.location.midnight(tomorrow).timestamp()
            tomorrow_sunrise = self.sunrise(tomorrow).timestamp()

            if solar_midnight < sunrise and tomorrow_solar_midnight < tomorrow_sunrise:
                # Solar midnight is before sunrise so use tomorrow's time
                solar_midnight = tomorrow_solar_midnight

        sunrise_or_sunset_next = False
        if now > sunrise and now < sunset and now > solar_noon:
            sunrise_or_sunset_next = True
        elif now > solar_midnight and now < sunrise:
            sunrise_or_sunset_next = True

        if now > sunrise:
            prev_ts = sunrise
        elif now > solar_noon:
            prev_ts = solar_noon
        elif now > sunset:
            prev_ts = sunset
        else:
            prev_ts = solar_midnight

        if now > sunset and now < solar_midnight:
            next_ts = solar_midnight
        elif now > solar_noon:
            next_ts = sunset
        elif now > sunrise:
            next_ts = solar_noon
        else:
            next_ts = sunrise

        if sunrise_or_sunset_next:
            k = 1
            h, x = prev_ts, next_ts
        else:
            k = -1
            h, x = next_ts, prev_ts

        percent = (0 - k) * ((now - h) / (h - x)) ** 2 + k

        brightness = percent
        if brightness < min_brightness:
            brightness = min_brightness
        elif brightness > max_brightness:
            brightness = max_brightness

        if percent > 0:
            kelvin = ((max_kelvin - min_kelvin) * percent) + min_kelvin
        else:
            kelvin = min_kelvin

        if kelvin > max_kelvin:
            kelvin = max_kelvin
        elif kelvin < min_kelvin:
            kelvin = min_kelvin

        return brightness, int(kelvin)
