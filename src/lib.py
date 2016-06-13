
class attrdict(dict):
    def __getattr__(self, key):
        return self[key]

if __name__ == '__main__':
    print "minimal testing: transport"
    testcases = dict(
        error=[ErrorReply(), 
               NoSuchDeviceErrorReply('device3'),
               NoSuchParamErrorReply('device2', 'param3'), 
               ParamReadonlyErrorReply('device1', 'param1'),
               UnsupportedFeatureErrorReply('feature5'), 
               NoSuchCommandErrorReply('device1','fance_command'), 
               CommandFailedErrorReply('device1','stop'), 
               InvalidParamValueErrorReply('device1','param2','STRING_Value'),
              ],
        reply=[Reply(), 
               ListDevicesReply('device1', 'device2'), 
               ListDeviceParamsReply('device', ['param1', 'param2']), 
               ReadValueReply('device2', 3.1415), 
               ReadParamReply('device1', 'param2', 2.718), 
               WriteParamReply('device1', 'param2', 2.718), 
               RequestAsyncDataReply('device1', 'XXX: what to put here?'), 
               AsyncDataUnit('device1', 'param2', 2.718), 
               ListOfFeaturesReply('feature1', 'feature2'), 
               ActivateFeatureReply(),
              ],
        request=[Request(), 
                 ListDevicesRequest(), 
                 ListDeviceParamsRequest('device1'), 
                 ReadValueRequest('device2'), 
                 ReadParamRequest('device1', 'param2'), 
                 WriteParamRequest('device1', 'param2', 2.718), 
                 RequestAsyncDataRequest('device1', ['param1', 'param2']), 
                 ListOfFeaturesRequest(), 
                 ActivateFeatureRequest('feature1'),
                ],
    )
    for msgtype, msgs in testcases.items():
        print "___ testing %ss ___" % msgtype
        for msg in msgs:
            print msg.__class__.__name__, 'is', msgtype,
            decoded = parse(msg)
            if decoded[0] != msgtype:
                print "\tFAIL, got %r but expected %r" %(decoded[0], msgtype)
            else:
                print "\tOk"
        print

