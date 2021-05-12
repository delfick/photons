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

        if now > sunrise and now < sunset:
            h = solar_noon
            k = 100
            if now < solar_noon:
                x = sunrise
            else:
                x = sunset
            y = 0

        else:
            h = solar_midnight
            k = -100
            if now < solar_midnight:
                x = sunset
            else:
                x = sunrise
            y = 0

        a = (y - k) / (h - x) ** 2
        percent = a * (now - h) ** 2 + k

        brightness = percent / 100
        if brightness < min_brightness:
            brightness = min_brightness
        elif brightness > max_brightness:
            brightness = max_brightness

        if percent > 0:
            kelvin = ((max_kelvin - min_kelvin) * (percent / 100)) + min_kelvin
        else:
            kelvin = min_kelvin

        if kelvin > max_kelvin:
            kelvin = max_kelvin
        elif kelvin < min_kelvin:
            kelvin = min_kelvin

        return brightness, int(kelvin)
