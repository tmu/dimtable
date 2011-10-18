// -------------------------------------------------------------------------------
// dimtable provides JS-functionality for dimtables. 
// 
// dimtables are multi-dimensional editable HTML tables that are directly tied to 
// database tables in the backend code.
//     
// Note: Javascript Module pattern is used here. 
//       http://www.wait-till-i.com/2007/07/24/show-love-to-the-module-pattern/
// -------------------------------------------------------------------------------
var dimtable = function() {

    // ----------------------------------
    // A few math functions 
    // TODO(teemu): move to own module
    // ----------------------------------
    var sum     = function(xs) { return xs.reduce(function(x,y) { return x+y; }, 0); };
    var product = function(xs) { return xs.reduce(function(x,y) { return x*y; }, 1); };
    // intdiv - integer division
    // Javascript hasn't integer division. See Stackoverflow for discussion:
    // http://stackoverflow.com/questions/4228356/integer-division-in-javascript
    var intdiv = function(x,y) { return x / y | 0; }


    // ----------------------------------
    // Cell index conversion
    // ----------------------------------
    var core = {
        dimindex_to_int: function(cellix, dimdata) {
            var rixes = cellix[0];
            var cixes = cellix[1];
            var rlens = dimdata.rdim_lengths;
            var clens = dimdata.cdim_lengths;
            var rsum = sum(rixes.map(
                function(r,i) { 
                    return r * product(rlens.slice(i+1)) * product(clens);
                }));
                
            var csum = sum(cixes.map(
                function(c, i) {
                    return c * product(clens.slice(i+1));
                }));
            return rsum + csum;
        },
        
        int_to_dimindex: function(integer, dimdata) {
            var v = integer;
            // copy (slice(0) and reverse length arrays (JS reverse is in-place)
            var rlens = dimdata.rdim_lengths.slice(0).reverse(); 
            var clens = dimdata.cdim_lengths.slice(0).reverse();          
            var cixes = [];
            clens.forEach(function(m) {
                              cixes.push(v % m);
                              v = intdiv(v, m);
                          });
            
            var rixes = [];
            rlens.forEach(function(m) {
                              rixes.push(v % m);
                              v = intdiv(v, m);
                          });
            return [rixes.reverse(), cixes.reverse()];
        } 
    };
    
    var EditableTable = function(args) {
        // TODO(teemu): doesn't support table prefix yet, but assumes 
        //              that prefix is always 'table'            

        var create_input = undefined 
        if ("create_input" in args) {
           create_input = args.create_input   
        } else {
           create_input = function(val, name) {
             return $('<input type="text"/>').val(val).attr({size: 3, maxlength: 3, name: name});
           };
        }


        var rdimN = $('input[name=table_rdim_dimN]').val();
        var cdimN = $('input[name=table_cdim_dimN]').val();
        var rdim_lengths = [];
        var cdim_lengths = [];

        for (i=0; i<rdimN; i++) {
            var v = $('input[name=table_rdim_length_' + i + ']').val();
            rdim_lengths[i] = parseInt(v);
        }

        for (i=0; i<cdimN; i++) {
            var v = $('input[name=table_cdim_length_' + i + ']').val();
            cdim_lengths[i] = parseInt(v);
        }
        
        var make_editable = function() {
            if ($(this).hasClass('edit')) return;
            
            var val = $(this).html();
            var name = $(this).attr('id');
          
            var input = create_input(val, name).addClass('detect-keys');
            
            $(this).html(input);
            $(this).addClass('edit').css('background-color', '#EDF5FF');
        };

        function edit() {
            make_editable.call($(this));
            $(this).find('input').focus();
        }

        var on_key_down = function(e) {
            var keyCode = e.keyCode || e.which; 
            var backwards = e.shiftKey;

            var cellid = $(this).attr('name');
            var ix = parseInt(cellid.slice(11));
            var dimdata= { rdim_lengths:rdim_lengths,
                           cdim_lengths:cdim_lengths
                         };
            
            var delta = undefined;
            var colcount = dimtable.math.product(dimdata.cdim_lengths);
            var rowcount = dimtable.math.product(dimdata.rdim_lengths);
            var cellcount = colcount * rowcount;

            if (keyCode == $.ui.keyCode.UP)    { delta = -colcount; }
            if (keyCode == $.ui.keyCode.DOWN)  { delta = +colcount; }
            if (keyCode == $.ui.keyCode.LEFT)  { delta = -1; }
            if (keyCode == $.ui.keyCode.RIGHT) { delta = +1; }
            if (keyCode == $.ui.keyCode.TAB)   { delta = backwards ? -1 : 1; }

            if (delta != undefined) {
                e.preventDefault();

                // Find next editable cell
                var newix = ix;
                while(true) {
                    newix = newix + delta;
                    if (0 <= newix && newix < cellcount) {
                        var cellid = "table_cell_" + newix;
                        var next = $('td[id="' + cellid + '"]');
                        if (next.hasClass('editable')) {
                            edit.call(next);   
                            break;
                        }
                    } else {
                        break;
                    }
                }
            }
        }; 

        $('td.editable').one('click', edit);
        $('input.detect-keys').live('keydown', on_key_down);
        
        return {
            on_key_down: on_key_down,
            edit: edit,
            make_editable: make_editable            
        };
    };
        
    // Public
    return {
        core: core,
        EditableTable: EditableTable,

        // TODO(teemu): temporarily expose these for debugging,
        //              should be moved somewhere else
        math: {
            sum: sum,
            product: product
        }
    };
}();
