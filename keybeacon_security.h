/* SPDX-License-Identifier: MIT */
#pragma once

#include <zephyr/bluetooth/gatt.h>

/* A connected, encrypted, bonded host's ZMK profile; -1 otherwise. */
int kbp_host_profile(struct bt_conn *conn);
bool kbp_is_input_host(struct bt_conn *conn);

ssize_t kbp_read(struct bt_conn *conn, const struct bt_gatt_attr *attr, void *buf,
                 uint16_t len, uint16_t offset, const void *data, uint16_t data_len,
                 bool input_status);

/* Pass a characteristic VALUE attribute so Zephyr also checks its permissions.
 * clear_inactive is only used on endpoint changes, never on typing events. */
void kbp_notify(const struct bt_gatt_attr *attr, const void *data, uint16_t len,
                bool input_status, bool clear_inactive);
