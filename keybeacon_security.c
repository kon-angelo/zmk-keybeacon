/* SPDX-License-Identifier: MIT */
#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/conn.h>
#include <zmk/ble.h>
#include <zmk/endpoints.h>

#include "keybeacon_security.h"

/* A protocol-compatible placeholder, never a snapshot of another host's input. */
static const uint8_t private_status[] = {0, 0, 'P', 'r', 'i', 'v', 'a', 't', 'e'};

struct bond_lookup {
    const bt_addr_le_t *peer;
    bool found;
};

static void find_bond(const struct bt_bond_info *info, void *user_data) {
    struct bond_lookup *lookup = user_data;
    if (bt_addr_le_eq(&info->addr, lookup->peer)) {
        lookup->found = true;
    }
}

int kbp_host_profile(struct bt_conn *conn) {
    struct bt_conn_info info;
    if (conn == NULL || bt_conn_get_info(conn, &info) != 0 ||
        info.type != BT_CONN_TYPE_LE || info.role != BT_CONN_ROLE_PERIPHERAL ||
        info.state != BT_CONN_STATE_CONNECTED || bt_conn_get_security(conn) < BT_SECURITY_L2) {
        return -1;
    }

    const bt_addr_le_t *peer = bt_conn_get_dst(conn);
    if (peer == NULL) {
        return -1;
    }
    struct bond_lookup lookup = {.peer = peer};
    bt_foreach_bond(info.id, find_bond, &lookup);
    if (!lookup.found) {
        return -1;
    }

    int profile = zmk_ble_profile_index(peer);
    return profile >= 0 && profile < ZMK_BLE_PROFILE_COUNT ? profile : -1;
}

bool kbp_is_input_host(struct bt_conn *conn) {
    int profile = kbp_host_profile(conn);
    if (profile < 0) {
        return false;
    }
#if defined(ZMK_KEYBEACON_HAS_LEGACY_ENDPOINT)
    struct zmk_endpoint_instance endpoint = zmk_endpoints_selected();
#else
    struct zmk_endpoint_instance endpoint = zmk_endpoint_get_selected();
#endif
    return endpoint.transport == ZMK_TRANSPORT_BLE &&
           endpoint.ble.profile_index == profile && zmk_ble_active_profile_index() == profile;
}

ssize_t kbp_read(struct bt_conn *conn, const struct bt_gatt_attr *attr, void *buf,
                 uint16_t len, uint16_t offset, const void *data, uint16_t data_len,
                 bool input_status) {
    if (kbp_host_profile(conn) < 0) {
        return BT_GATT_ERR(BT_ATT_ERR_AUTHORIZATION);
    }
    if (input_status && !kbp_is_input_host(conn)) {
        data = private_status;
        data_len = sizeof(private_status);
    }
    return bt_gatt_attr_read(conn, attr, buf, len, offset, data, data_len);
}

struct notify_context {
    const struct bt_gatt_attr *attr;
    const void *data;
    uint16_t len;
    bool input_status;
    bool clear_inactive;
};

static void notify_host(struct bt_conn *conn, void *user_data) {
    const struct notify_context *ctx = user_data;
    if (kbp_host_profile(conn) < 0 ||
        !bt_gatt_is_subscribed(conn, ctx->attr, BT_GATT_CCC_NOTIFY)) {
        return;
    }

    const void *data = ctx->data;
    uint16_t len = ctx->len;
    if (ctx->input_status && !kbp_is_input_host(conn)) {
        if (!ctx->clear_inactive) {
            return;
        }
        data = private_status;
        len = sizeof(private_status);
    }
    bt_gatt_notify(conn, ctx->attr, data, len);
}

void kbp_notify(const struct bt_gatt_attr *attr, const void *data, uint16_t len,
                bool input_status, bool clear_inactive) {
    struct notify_context ctx = {
        .attr = attr,
        .data = data,
        .len = len,
        .input_status = input_status,
        .clear_inactive = clear_inactive,
    };
    bt_conn_foreach(BT_CONN_TYPE_LE, notify_host, &ctx);
}
