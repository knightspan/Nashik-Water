#pragma once
#include <stdarg.h>
namespace Eloquent {
    namespace ML {
        namespace Port {
            class WaterStateTree {
                public:
                    /**
                    * Predict class for features vector
                    */
                    int predict(float *x) {
                        if (x[2] <= 1.6939718127250671) {
                            if (x[2] <= 1.354601502418518) {
                                if (x[2] <= 1.222217321395874) {
                                    if (x[0] <= 0.6639000177383423) {
                                        if (x[0] <= -0.14400000125169754) {
                                            return 0;
                                        }

                                        else {
                                            return 0;
                                        }
                                    }

                                    else {
                                        if (x[1] <= 0.9626210629940033) {
                                            return 1;
                                        }

                                        else {
                                            return 0;
                                        }
                                    }
                                }

                                else {
                                    if (x[1] <= 0.8748985528945923) {
                                        if (x[3] <= -6.452500104904175) {
                                            return 0;
                                        }

                                        else {
                                            return 1;
                                        }
                                    }

                                    else {
                                        if (x[0] <= -0.7989999949932098) {
                                            return 2;
                                        }

                                        else {
                                            return 0;
                                        }
                                    }
                                }
                            }

                            else {
                                if (x[4] <= -0.6349999904632568) {
                                    if (x[0] <= 0.1607000008225441) {
                                        if (x[2] <= 1.5487687587738037) {
                                            return 0;
                                        }

                                        else {
                                            return 1;
                                        }
                                    }

                                    else {
                                        if (x[1] <= 0.8981083333492279) {
                                            return 0;
                                        }

                                        else {
                                            return 1;
                                        }
                                    }
                                }

                                else {
                                    if (x[0] <= 0.24040000140666962) {
                                        if (x[1] <= 0.8893878161907196) {
                                            return 1;
                                        }

                                        else {
                                            return 0;
                                        }
                                    }

                                    else {
                                        if (x[0] <= 0.7084000110626221) {
                                            return 1;
                                        }

                                        else {
                                            return 0;
                                        }
                                    }
                                }
                            }
                        }

                        else {
                            if (x[1] <= 1.2879239916801453) {
                                if (x[2] <= 2.6371008157730103) {
                                    if (x[1] <= 1.0528533458709717) {
                                        if (x[1] <= 0.9989921152591705) {
                                            return 1;
                                        }

                                        else {
                                            return 0;
                                        }
                                    }

                                    else {
                                        if (x[3] <= -21.674999237060547) {
                                            return 2;
                                        }

                                        else {
                                            return 1;
                                        }
                                    }
                                }

                                else {
                                    if (x[3] <= -25.275833129882812) {
                                        if (x[0] <= -0.23269999772310257) {
                                            return 2;
                                        }

                                        else {
                                            return 1;
                                        }
                                    }

                                    else {
                                        if (x[3] <= 36.52000045776367) {
                                            return 1;
                                        }

                                        else {
                                            return 2;
                                        }
                                    }
                                }
                            }

                            else {
                                if (x[1] <= 1.2967906594276428) {
                                    if (x[3] <= 1.809999942779541) {
                                        return 2;
                                    }

                                    else {
                                        return 1;
                                    }
                                }

                                else {
                                    return 2;
                                }
                            }
                        }
                    }

                    /**
                    * Predict readable class name
                    */
                    const char* predictLabel(float *x) {
                        return idxToLabel(predict(x));
                    }

                    /**
                    * Convert class idx to readable name
                    */
                    const char* idxToLabel(uint8_t classIdx) {
                        switch (classIdx) {
                            case 0:
                            return "NORMAL";
                            case 1:
                            return "NATURAL";
                            case 2:
                            return "ALERT";
                            default:
                            return "Houston we have a problem";
                        }
                    }

                protected:
                };
            }
        }
    }