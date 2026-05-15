export function dispatchJsonCommand(controller, payload) {
    if (typeof payload === 'string') {
        controller.dispatchJson(payload);
        return;
    }
    controller.dispatch(payload);
}
export function bindWebSocketCommandStream(controller, socket) {
    socket.addEventListener('message', (event) => {
        if (typeof event.data !== 'string')
            return;
        controller.dispatchJson(event.data);
    });
}
