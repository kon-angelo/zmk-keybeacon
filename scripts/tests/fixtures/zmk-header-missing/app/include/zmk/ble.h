/* Fake ZMK ble.h — common across all four fixtures.
 * Carries the profile-related symbols that zmk-keybeacon depends on.
 */

bool zmk_ble_active_profile_is_connected(void);
int  zmk_ble_active_profile_index(void);
bool zmk_ble_active_profile_is_open(void);
int  zmk_ble_profile_index(const bt_addr_le_t *addr);
