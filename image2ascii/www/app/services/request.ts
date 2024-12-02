import RequestManager from "@ember-data/request";
import Fetch from "@ember-data/request/fetch";

export default class RequestManagerService extends RequestManager {
    constructor(args?: Record<string | symbol, unknown>) {
        super(args);
        this.use([Fetch]);
    }
}

declare module "@ember/service" {
    interface Registry {
        request: RequestManagerService;
    }
}
