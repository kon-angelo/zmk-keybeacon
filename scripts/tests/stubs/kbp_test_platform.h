/* Minimal Bluetooth/ZMK API doubles for the real keybeacon_security.c. */
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <sys/types.h>

#define BT_CONN_TYPE_LE 1
#define BT_CONN_TYPE_BR 2
#define BT_CONN_ROLE_CENTRAL 0
#define BT_CONN_ROLE_PERIPHERAL 1
#define BT_CONN_STATE_CONNECTED 1
#define BT_SECURITY_L1 1
#define BT_SECURITY_L2 2
#define BT_ATT_ERR_AUTHORIZATION 8
#define BT_ATT_ERR_INVALID_OFFSET 7
#define BT_GATT_ERR(err) (-(err))
#define BT_GATT_CCC_NOTIFY 1
#define ZMK_BLE_PROFILE_COUNT 3
#define ZMK_TRANSPORT_NONE 0
#define ZMK_TRANSPORT_USB 1
#define ZMK_TRANSPORT_BLE 2

typedef struct {
    int profile;
    bool bonded;
    unsigned int address;
} bt_addr_le_t;

struct bt_bond_info { bt_addr_le_t addr; };

struct bt_conn_info {
    int type;
    int role;
    int state;
    uint8_t id;
};

struct bt_conn {
    struct bt_conn_info info;
    bt_addr_le_t peer;
    int security;
    bool subscribed;
    bool info_error;
    bool missing_peer;
    unsigned int notifications;
    uint8_t last_payload[64];
    uint16_t last_len;
};

struct bt_gatt_attr { int handle; };
struct zmk_endpoint_instance {
    int transport;
    struct { int profile_index; } ble;
};

int bt_conn_get_info(const struct bt_conn *, struct bt_conn_info *);
int bt_conn_get_security(const struct bt_conn *);
const bt_addr_le_t *bt_conn_get_dst(const struct bt_conn *);
bool bt_addr_le_eq(const bt_addr_le_t *, const bt_addr_le_t *);
void bt_foreach_bond(uint8_t, void (*)(const struct bt_bond_info *, void *), void *);
int zmk_ble_profile_index(const bt_addr_le_t *);
int zmk_ble_active_profile_index(void);
struct zmk_endpoint_instance zmk_endpoint_get_selected(void);
struct zmk_endpoint_instance zmk_endpoints_selected(void);
ssize_t bt_gatt_attr_read(struct bt_conn *, const struct bt_gatt_attr *, void *,
                          uint16_t, uint16_t, const void *, uint16_t);
bool bt_gatt_is_subscribed(struct bt_conn *, const struct bt_gatt_attr *, uint16_t);
int bt_gatt_notify(struct bt_conn *, const struct bt_gatt_attr *, const void *, uint16_t);
void bt_conn_foreach(int, void (*)(struct bt_conn *, void *), void *);
