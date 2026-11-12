/* Exercise the production access-control and notification code with API doubles. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "keybeacon_security.h"

static struct bt_conn peers[6];
static struct zmk_endpoint_instance endpoint;
static int active_profile;
static const struct bt_gatt_attr value_attr = {.handle = 2};
static const uint8_t input[] = {4, 0x22, 'S', 'e', 'c', 'r', 'e', 't'};
static const uint8_t hidden[] = {0, 0, 'P', 'r', 'i', 'v', 'a', 't', 'e'};
static const uint8_t battery[] = {75, 90};

int bt_conn_get_info(const struct bt_conn *conn, struct bt_conn_info *info) {
    *info = conn->info;
    return conn->info_error ? -1 : 0;
}
int bt_conn_get_security(const struct bt_conn *conn) { return conn->security; }
const bt_addr_le_t *bt_conn_get_dst(const struct bt_conn *conn) {
    return conn->missing_peer ? NULL : &conn->peer;
}
bool bt_addr_le_eq(const bt_addr_le_t *a, const bt_addr_le_t *b) {
    return a->address == b->address;
}
void bt_foreach_bond(uint8_t id, void (*callback)(const struct bt_bond_info *, void *),
                      void *user_data) {
    if (id != 0) { return; }
    for (unsigned int i = 0; i < sizeof(peers) / sizeof(peers[0]); i++) {
        if (peers[i].peer.bonded) {
            struct bt_bond_info info = {.addr = peers[i].peer};
            callback(&info, user_data);
        }
    }
}
int zmk_ble_profile_index(const bt_addr_le_t *peer) { return peer->profile; }
int zmk_ble_active_profile_index(void) { return active_profile; }
struct zmk_endpoint_instance zmk_endpoint_get_selected(void) { return endpoint; }
struct zmk_endpoint_instance zmk_endpoints_selected(void) { return endpoint; }

ssize_t bt_gatt_attr_read(struct bt_conn *conn, const struct bt_gatt_attr *attr,
                          void *buf, uint16_t len, uint16_t offset,
                          const void *data, uint16_t data_len) {
    (void)conn;
    assert(attr == &value_attr);
    if (offset > data_len) { return BT_GATT_ERR(BT_ATT_ERR_INVALID_OFFSET); }
    uint16_t count = len < data_len - offset ? len : data_len - offset;
    memcpy(buf, (const uint8_t *)data + offset, count);
    return count;
}
bool bt_gatt_is_subscribed(struct bt_conn *conn, const struct bt_gatt_attr *attr,
                           uint16_t ccc) {
    assert(attr == &value_attr && ccc == BT_GATT_CCC_NOTIFY);
    return conn->subscribed;
}
int bt_gatt_notify(struct bt_conn *conn, const struct bt_gatt_attr *attr,
                    const void *data, uint16_t len) {
    assert(conn != NULL && attr == &value_attr && len <= sizeof(conn->last_payload));
    conn->notifications++;
    memcpy(conn->last_payload, data, len);
    conn->last_len = len;
    return 0;
}
void bt_conn_foreach(int type, void (*callback)(struct bt_conn *, void *), void *data) {
    for (unsigned int i = 0; i < sizeof(peers) / sizeof(peers[0]); i++) {
        if (peers[i].info.type == type) { callback(&peers[i], data); }
    }
}

static void setup(void) {
    memset(peers, 0, sizeof(peers));
    for (unsigned int i = 0; i < sizeof(peers) / sizeof(peers[0]); i++) {
        peers[i].info = (struct bt_conn_info){BT_CONN_TYPE_LE, BT_CONN_ROLE_PERIPHERAL,
                                             BT_CONN_STATE_CONNECTED, 0};
        peers[i].peer = (bt_addr_le_t){(int)i, true, i};
        peers[i].security = BT_SECURITY_L2;
        peers[i].subscribed = true;
    }
    /* Active host, inactive host, unsubscribed host, attacker, split peer,
     * and a bonded host reconnecting before encryption is established. */
    peers[2].subscribed = false;
    peers[3].peer = (bt_addr_le_t){0, false, 3};
    peers[4].peer.profile = 0;
    peers[4].info.role = BT_CONN_ROLE_CENTRAL;
    peers[5].peer.profile = 0;
    peers[5].security = BT_SECURITY_L1;
    endpoint = (struct zmk_endpoint_instance){ZMK_TRANSPORT_BLE, {0}};
    active_profile = 0;
}

static void expect_read(struct bt_conn *conn, bool is_input, const uint8_t *expected,
                         uint16_t expected_len) {
    uint8_t buf[64] = {0};
    ssize_t len = kbp_read(conn, &value_attr, buf, sizeof(buf), 0, input, sizeof(input), is_input);
    assert(len == expected_len && memcmp(buf, expected, expected_len) == 0);
}

static void expect_denied(struct bt_conn *conn) {
    uint8_t buf[64] = {0};
    assert(kbp_host_profile(conn) == -1);
    assert(!kbp_is_input_host(conn));
    for (int input_status = 0; input_status <= 1; input_status++) {
        assert(kbp_read(conn, &value_attr, buf, sizeof(buf), 0, input, sizeof(input),
                         input_status) == BT_GATT_ERR(BT_ATT_ERR_AUTHORIZATION));
    }
}

static void test_authorization(void) {
    setup();
    assert(kbp_host_profile(&peers[0]) == 0 && kbp_host_profile(&peers[1]) == 1);
    expect_denied(NULL);
    for (int i = 3; i < 6; i++) { expect_denied(&peers[i]); }
    struct bt_conn invalid = peers[0];
    invalid.info_error = true; expect_denied(&invalid);
    invalid = peers[0]; invalid.missing_peer = true; expect_denied(&invalid);
    invalid = peers[0]; invalid.info.type = BT_CONN_TYPE_BR; expect_denied(&invalid);
    invalid = peers[0]; invalid.info.state = 0; expect_denied(&invalid);
    invalid = peers[0]; invalid.info.id = 1; expect_denied(&invalid);
    invalid = peers[0]; invalid.peer.profile = -1; expect_denied(&invalid);
    invalid = peers[0]; invalid.peer.profile = ZMK_BLE_PROFILE_COUNT; expect_denied(&invalid);
}

static void test_reads_and_profile_switch(void) {
    setup();
    expect_read(&peers[0], true, input, sizeof(input));
    expect_read(&peers[1], true, hidden, sizeof(hidden));
    expect_read(&peers[1], false, input, sizeof(input));
    /* Fail closed while ZMK updates the profile and selected endpoint. */
    active_profile = 1;
    expect_read(&peers[0], true, hidden, sizeof(hidden));
    expect_read(&peers[1], true, hidden, sizeof(hidden));
    endpoint.ble.profile_index = 1;
    expect_read(&peers[1], true, input, sizeof(input));
    endpoint.transport = ZMK_TRANSPORT_USB;
    expect_read(&peers[1], true, hidden, sizeof(hidden));
    endpoint.transport = ZMK_TRANSPORT_NONE;
    expect_read(&peers[1], true, hidden, sizeof(hidden));
    uint8_t buf[32];
    assert(kbp_read(&peers[1], &value_attr, buf, sizeof(buf), 2, input, sizeof(input), true) == 7);
    assert(memcmp(buf, "Private", 7) == 0);
}

static void test_notifications(void) {
    setup();
    kbp_notify(&value_attr, input, sizeof(input), true, false);
    assert(peers[0].notifications == 1 && peers[0].last_len == sizeof(input));
    assert(memcmp(peers[0].last_payload, input, sizeof(input)) == 0);
    for (int i = 1; i < 6; i++) { assert(peers[i].notifications == 0); }

    active_profile = endpoint.ble.profile_index = 1;
    kbp_notify(&value_attr, input, sizeof(input), true, true);
    assert(peers[0].notifications == 2 && peers[0].last_len == sizeof(hidden));
    assert(memcmp(peers[0].last_payload, hidden, sizeof(hidden)) == 0);
    assert(peers[1].notifications == 1 && peers[1].last_len == sizeof(input));
    /* No input-event timing signal goes to the inactive host. */
    for (int i = 0; i < 20; i++) { kbp_notify(&value_attr, input, sizeof(input), true, false); }
    assert(peers[0].notifications == 2 && peers[1].notifications == 21);
    for (int i = 2; i < 6; i++) { assert(peers[i].notifications == 0); }

    endpoint.transport = ZMK_TRANSPORT_USB;
    kbp_notify(&value_attr, input, sizeof(input), true, true);
    assert(memcmp(peers[1].last_payload, hidden, sizeof(hidden)) == 0);
    kbp_notify(&value_attr, input, sizeof(input), true, false);
    assert(peers[0].notifications == 3 && peers[1].notifications == 22);

    kbp_notify(&value_attr, battery, sizeof(battery), false, false);
    assert(peers[0].notifications == 4 && peers[1].notifications == 23);
    assert(memcmp(peers[1].last_payload, battery, sizeof(battery)) == 0);
    for (int i = 2; i < 6; i++) { assert(peers[i].notifications == 0); }

    /* Losing encryption or removing a bond revokes even non-input access. */
    peers[0].security = BT_SECURITY_L1;
    peers[1].peer.bonded = false;
    kbp_notify(&value_attr, battery, sizeof(battery), false, false);
    assert(peers[0].notifications == 4 && peers[1].notifications == 23);
}

int main(void) {
    test_authorization();
    test_reads_and_profile_switch();
    test_notifications();
    puts("KeyBeacon authorization, read privacy, and notification isolation passed");
    return 0;
}
